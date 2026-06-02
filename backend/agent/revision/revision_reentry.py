from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any, Literal

from ..pipeline.agent_pipeline import AgentPipeline
from .revision_impact import (
    deprecate_replaced_tests,
    related_requirements,
    revision_requirement_text,
    selected_coverage_items,
    selected_requirements,
    selected_test_cases,
)
from .revision_utils import (
    ChangeSet,
    ReentryResult,
    RevisionRunnerError,
    agent_prompt_records_to_evidence,
    bounded_int,
    coverage_technique,
    mark_revision,
    merge_items,
    model_dump_item,
    model_dump_list,
    preserve_existing_coverage_ids,
    split_created_updated,
    string_list,
    dedupe_by_id,
)


@dataclass
class ReentryContext:
    revision: dict[str, Any]
    state: dict[str, list[dict[str, Any]]]
    impact: dict[str, Any]
    impacted_coverage: list[dict[str, Any]]
    impacted_tests: list[dict[str, Any]]
    current_state: dict[str, Any] | None
    rag_context: str | None
    pipeline: AgentPipeline

    @property
    def session_id(self) -> str:
        return str(self.revision.get("session_id") or "")

    @property
    def revision_id(self) -> str:
        return str(self.revision.get("revision_id") or "")

    @property
    def effective_rag_context(self) -> str:
        return self.rag_context or str((self.current_state or {}).get("rag_context") or "")


@dataclass(frozen=True)
class OutputSpec:
    collection: str
    attr: str
    id_field: str
    mode: Literal["split", "update"] = "split"
    mark_revision: bool = True


async def run_pipeline_step(
    ctx: ReentryContext,
    stage: str,
    call: Callable[[], Awaitable[Any]],
    outputs: list[OutputSpec],
    evidence_summary: Callable[[Any, ChangeSet], dict[str, Any]],
) -> ReentryResult:
    pipeline_result = await call()
    changes = ChangeSet()

    for spec in outputs:
        items = model_dump_list(list(getattr(pipeline_result, spec.attr)))
        if spec.mark_revision:
            mark_revision(items, ctx.revision, "pipeline_regenerated")
        if spec.mode == "update":
            changes.add_updated(spec.collection, items)
            continue
        created, updated = split_created_updated(
            items,
            ctx.state.get(spec.collection, []),
            spec.id_field,
        )
        changes.add_created(spec.collection, created)
        changes.add_updated(spec.collection, updated)

    evidence = agent_prompt_records_to_evidence(
        ctx.session_id,
        pipeline_result.prompts_used,
        ctx.revision_id,
        evidence_summary(pipeline_result, changes),
        f"Revision re-entered AgentPipeline.{stage}.",
    )
    return ReentryResult(changes=changes, evidence=evidence, pipeline_result=pipeline_result)


async def rerun_from_impact(ctx: ReentryContext) -> ReentryResult:
    stage = str(ctx.impact.get("reentry_stage") or "")
    try:
        rerunner = RERUNNERS[stage]
    except KeyError as exc:
        raise RevisionRunnerError(f"unsupported reentry_stage: {stage}", 502) from exc
    return await rerunner(ctx)


async def rerun_analysis(ctx: ReentryContext) -> ReentryResult:
    return ReentryResult()


async def rerun_oracle(ctx: ReentryContext) -> ReentryResult:
    test_cases = ctx.impacted_tests or selected_test_cases(ctx.impact, ctx.state)
    if not test_cases:
        raise RevisionRunnerError("oracle reentry requires at least one affected test case", 422)

    return await run_pipeline_step(
        ctx,
        stage="generate_oracles",
        call=lambda: ctx.pipeline.generate_oracles(
            test_cases,
            requirements=related_requirements(ctx.state, ctx.revision, [], test_cases),
            rag_context=ctx.effective_rag_context,
        ),
        outputs=[
            OutputSpec(
                collection="oracle_results",
                attr="oracle_results",
                id_field="test_id",
                mode="update",
            )
        ],
        evidence_summary=lambda result, changes: {
            "stage": "oracle",
            "oracle_result_count": len(result.oracle_results),
        },
    )


async def rerun_fsm(ctx: ReentryContext) -> ReentryResult:
    coverage_items = ctx.impacted_coverage or selected_coverage_items(ctx.impact, ctx.state, [])
    result = await run_pipeline_step(
        ctx,
        stage="generate_fsm",
        call=lambda: ctx.pipeline.generate_fsm(
            requirements=related_requirements(ctx.state, ctx.revision, coverage_items, ctx.impacted_tests),
            parsed_requirements=ctx.state.get("parsed_requirements", []),
            coverage_items=coverage_items,
            rag_context=ctx.effective_rag_context,
        ),
        outputs=[
            OutputSpec(
                collection="test_cases",
                attr="test_cases",
                id_field="test_id",
                mode="split",
            )
        ],
        evidence_summary=lambda pipeline_result, changes: {
            "stage": "fsm",
            "test_case_count": len(pipeline_result.test_cases),
        },
    )

    fsm_payload = model_dump_item(result.pipeline_result.fsm)
    result.changes.set_updated("fsm", fsm_payload)
    result.changes.add_deprecated(
        "test_cases",
        deprecate_replaced_tests(ctx.impacted_tests, result.changes, ctx.revision),
    )
    return result


async def rerun_generate(ctx: ReentryContext) -> ReentryResult:
    coverage_items = selected_coverage_items(ctx.impact, ctx.state, ctx.impacted_coverage)
    normal_items = [item for item in coverage_items if coverage_technique(item) != "FSM"]
    fsm_items = [item for item in coverage_items if coverage_technique(item) == "FSM"]

    result = ReentryResult()

    if normal_items:
        normal_result = await run_pipeline_step(
            ctx,
            stage="generate_tests",
            call=lambda: ctx.pipeline.generate_tests(
                [agent_coverage_item(item, ctx.state) for item in normal_items],
                agent_risk_items(ctx.state, normal_items),
                ctx.effective_rag_context,
            ),
            outputs=[
                OutputSpec(
                    collection="test_cases",
                    attr="test_cases",
                    id_field="test_id",
                    mode="split",
                )
            ],
            evidence_summary=lambda pipeline_result, changes: {
                "stage": "generate",
                "test_case_count": len(pipeline_result.test_cases),
            },
        )
        result.merge(normal_result)

    if fsm_items:
        result.merge(await rerun_fsm(replace(ctx, impacted_coverage=fsm_items)))

    result.changes.add_deprecated(
        "test_cases",
        deprecate_replaced_tests(ctx.impacted_tests, result.changes, ctx.revision),
    )
    return result


async def rerun_strategy(ctx: ReentryContext) -> ReentryResult:
    coverage_items = selected_coverage_items(ctx.impact, ctx.state, ctx.impacted_coverage)
    if not coverage_items:
        raise RevisionRunnerError("strategy reentry requires affected coverage items", 422)

    pipeline_result = await ctx.pipeline.assign_strategy(
        coverage_goals_from_coverage_items(coverage_items),
        analyzed_requirements_for_items(ctx.state, coverage_items),
        agent_risk_items(ctx.state, coverage_items),
        ctx.effective_rag_context,
    )
    regenerated_coverage = model_dump_list(list(pipeline_result.coverage_items))
    regenerated_coverage = preserve_existing_coverage_ids(regenerated_coverage, coverage_items)
    mark_revision(regenerated_coverage, ctx.revision, "pipeline_regenerated")

    created, updated = split_created_updated(
        regenerated_coverage,
        ctx.state.get("coverage_items", []),
        "coverage_item_id",
    )
    strategy_result = ReentryResult(pipeline_result=pipeline_result)
    strategy_result.changes.add_created("coverage_items", created)
    strategy_result.changes.add_updated("coverage_items", updated)
    strategy_result.evidence.extend(
        agent_prompt_records_to_evidence(
            ctx.session_id,
            pipeline_result.prompts_used,
            ctx.revision_id,
            {
                "stage": "strategy",
                "coverage_item_count": len(regenerated_coverage),
            },
            "Revision re-entered AgentPipeline.assign_strategy.",
        )
    )
    new_coverage = _changed_items(strategy_result.changes, "coverage_items")
    next_state = {
        **ctx.state,
        "coverage_items": merge_items(ctx.state.get("coverage_items", []), new_coverage, "coverage_item_id"),
    }
    next_impact = {
        **ctx.impact,
        "affected_ids": {
            **ctx.impact.get("affected_ids", {}),
            "coverage_items": [item.get("coverage_item_id") for item in new_coverage],
        },
    }
    strategy_result.merge(
        await rerun_generate(
            replace(
                ctx,
                state=next_state,
                impact=next_impact,
                impacted_coverage=new_coverage,
            )
        )
    )
    return strategy_result


async def rerun_risk(ctx: ReentryContext) -> ReentryResult:
    requirements = analyzed_requirements_for_items(ctx.state, selected_requirements(ctx.impact, ctx.state))
    if not requirements:
        raise RevisionRunnerError("risk reentry requires affected analyzed requirements", 422)

    risk_result = await run_pipeline_step(
        ctx,
        stage="analyze_risk",
        call=lambda: ctx.pipeline.analyze_risk(requirements, ctx.effective_rag_context),
        outputs=[
            OutputSpec(
                collection="risk_results",
                attr="risk_analysis",
                id_field="requirement_id",
                mode="update",
                mark_revision=False,
            )
        ],
        evidence_summary=lambda pipeline_result, changes: {
            "stage": "risk",
            "risk_count": len(pipeline_result.risk_analysis),
        },
    )
    risk_items = risk_result.changes.updated.get("risk_results", [])
    risk_result.merge(
        await rerun_strategy(
            replace(
                ctx,
                state={
                    **ctx.state,
                    "risk_results": merge_items(ctx.state.get("risk_results", []), risk_items, "requirement_id"),
                },
                impacted_coverage=selected_coverage_items(ctx.impact, ctx.state, []),
            )
        )
    )
    return risk_result


async def rerun_parse(ctx: ReentryContext) -> ReentryResult:
    requirement_text = revision_requirement_text(ctx.revision, ctx.state)
    if not requirement_text:
        raise RevisionRunnerError("parse reentry requires revised requirement text", 422)

    result = ReentryResult()
    parse_result = await run_pipeline_step(
        ctx,
        stage="parse_requirements",
        call=lambda: ctx.pipeline.parse_requirements(requirement_text, ctx.effective_rag_context),
        outputs=[
            OutputSpec("parsed_requirements", "requirements", "requirement_id", mode="update", mark_revision=False),
            OutputSpec("requirements", "analyzed_requirements", "requirement_id", mode="update", mark_revision=False),
        ],
        evidence_summary=lambda pipeline_result, changes: {
            "stage": "parse",
            "parsed_requirement_count": len(pipeline_result.requirements),
        },
    )
    result.merge(parse_result)

    analyzed_requirements = parse_result.pipeline_result.analyzed_requirements
    risk_result = await run_pipeline_step(
        ctx,
        stage="analyze_risk",
        call=lambda: ctx.pipeline.analyze_risk(analyzed_requirements, ctx.effective_rag_context),
        outputs=[OutputSpec("risk_results", "risk_analysis", "requirement_id", mode="update", mark_revision=False)],
        evidence_summary=lambda pipeline_result, changes: {
            "stage": "risk",
            "risk_count": len(pipeline_result.risk_analysis),
        },
    )
    result.merge(risk_result)

    coverage_result = await run_pipeline_step(
        ctx,
        stage="identify_coverage",
        call=lambda: ctx.pipeline.identify_coverage(
            analyzed_requirements,
            risk_result.pipeline_result.risk_analysis,
            ctx.effective_rag_context,
        ),
        outputs=[],
        evidence_summary=lambda pipeline_result, changes: {
            "stage": "coverage",
            "coverage_goal_count": len(pipeline_result.coverage_goals),
        },
    )
    result.merge(coverage_result)

    strategy_pipeline_result = await ctx.pipeline.assign_strategy(
        coverage_result.pipeline_result.coverage_goals,
        analyzed_requirements,
        risk_result.pipeline_result.risk_analysis,
        ctx.effective_rag_context,
    )
    regenerated_coverage = model_dump_list(list(strategy_pipeline_result.coverage_items))
    regenerated_coverage = preserve_existing_coverage_ids(
        regenerated_coverage,
        selected_coverage_items(ctx.impact, ctx.state, []),
    )
    mark_revision(regenerated_coverage, ctx.revision, "pipeline_regenerated")
    strategy_result = ReentryResult(pipeline_result=strategy_pipeline_result)
    strategy_result.changes.add_updated("coverage_items", regenerated_coverage)
    strategy_result.evidence.extend(
        agent_prompt_records_to_evidence(
            ctx.session_id,
            strategy_pipeline_result.prompts_used,
            ctx.revision_id,
            {
                "stage": "strategy",
                "coverage_item_count": len(regenerated_coverage),
            },
            "Revision re-entered AgentPipeline.assign_strategy.",
        )
    )
    result.merge(strategy_result)

    generate_result = await run_pipeline_step(
        ctx,
        stage="generate_tests",
        call=lambda: ctx.pipeline.generate_tests(
            regenerated_coverage,
            risk_result.pipeline_result.risk_analysis,
            ctx.effective_rag_context,
        ),
        outputs=[OutputSpec("test_cases", "test_cases", "test_id", mode="update")],
        evidence_summary=lambda pipeline_result, changes: {
            "stage": "generate",
            "test_case_count": len(pipeline_result.test_cases),
        },
    )
    result.merge(generate_result)
    return result


def agent_coverage_item(item: dict[str, Any], state: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    coverage_id = str(item.get("coverage_item_id") or "")
    strategy = _strategy_for_coverage(state, coverage_id)
    technique = coverage_technique(item)
    return {
        "coverage_item_id": coverage_id,
        "coverage_goal_id": str(item.get("coverage_goal_id") or coverage_id),
        "requirement_id": str(item.get("requirement_id") or ""),
        "technique": technique if technique in {"EP", "BVA", "DT"} else "EP",
        "description": str(item.get("description") or item.get("goal") or "Regenerate revised coverage item"),
        "conditions": string_list(item.get("conditions") or item.get("related_conditions")),
        "data_ranges": string_list(item.get("data_ranges")),
        "input_fields": string_list(item.get("input_fields") or item.get("related_inputs")),
        "expected_action": str(item.get("expected_action") or ""),
        "strategy_rationale": str(
            item.get("strategy_rationale")
            or strategy.get("reason")
            or "Designer revision requires downstream regeneration."
        ),
        "technique_reason": str(
            item.get("technique_reason")
            or strategy.get("reason")
            or "Technique retained from revised coverage item."
        ),
    }


def agent_risk_items(
    state: dict[str, list[dict[str, Any]]],
    coverage_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirement_ids = {
        str(item.get("requirement_id"))
        for item in coverage_items
        if item.get("requirement_id")
    }
    result: list[dict[str, Any]] = []
    for item in state.get("risk_results", []):
        requirement_id = str(item.get("requirement_id") or item.get("target_id") or "")
        if requirement_ids and requirement_id not in requirement_ids:
            continue
        impact = bounded_int(item.get("impact"), 3)
        likelihood = bounded_int(item.get("likelihood"), 3)
        risk_score = impact * likelihood
        risk_level = "High" if risk_score >= 15 else "Medium" if risk_score >= 8 else "Low"
        result.append(
            {
                "requirement_id": requirement_id,
                "impact": impact,
                "likelihood": likelihood,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "test_priority": {"High": "P1", "Medium": "P2", "Low": "P3"}[risk_level],
                "risk_reason": str(
                    item.get("risk_reason")
                    or item.get("reason")
                    or "Risk inherited from current state."
                ),
            }
        )
    return result


def analyzed_requirements_for_items(
    state: dict[str, list[dict[str, Any]]],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirement_ids = {
        str(item.get("requirement_id"))
        for item in items
        if item.get("requirement_id")
    }
    if not requirement_ids:
        requirement_ids = {
            str(item.get("requirement_id"))
            for item in state.get("parsed_requirements", [])
            if item.get("requirement_id")
        }
    existing = [
        item for item in state.get("parsed_requirements", [])
        if str(item.get("requirement_id") or "") in requirement_ids
    ]

    analyzed: list[dict[str, Any]] = []
    for item in existing or items:
        analyzed.append(
            {
                "requirement_id": str(item.get("requirement_id") or ""),
                "module": str(item.get("module") or "revision"),
                "description": str(item.get("description") or item.get("raw_text") or item.get("text") or ""),
                "input_fields": string_list(item.get("input_fields") or item.get("related_inputs")),
                "data_ranges": string_list(item.get("data_ranges")),
                "conditions": string_list(item.get("conditions") or item.get("related_conditions")),
                "business_rules": string_list(item.get("business_rules")),
                "expected_action": str(item.get("expected_action") or ""),
            }
        )
    return dedupe_by_id(analyzed, "requirement_id")


def coverage_goals_from_coverage_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "coverage_goal_id": str(item.get("coverage_goal_id") or item.get("coverage_item_id") or ""),
            "requirement_id": str(item.get("requirement_id") or ""),
            "goal": str(item.get("description") or item.get("expected_action") or "Regenerate revised coverage goal"),
            "related_inputs": string_list(item.get("input_fields") or item.get("related_inputs")),
            "related_conditions": string_list(item.get("conditions") or item.get("related_conditions")),
            "expected_action": str(item.get("expected_action") or ""),
        }
        for item in items
    ]


def _strategy_for_coverage(state: dict[str, list[dict[str, Any]]], coverage_id: str) -> dict[str, Any]:
    for strategy in state.get("strategies", []):
        if str(strategy.get("coverage_item_id") or "") == coverage_id:
            return strategy
    return {}


def _changed_items(changes: ChangeSet, collection: str) -> list[dict[str, Any]]:
    return [
        *changes.created.get(collection, []),
        *changes.updated.get(collection, []),
    ]


RERUNNERS = {
    "parse": rerun_parse,
    "risk": rerun_risk,
    "strategy": rerun_strategy,
    "generate": rerun_generate,
    "fsm": rerun_fsm,
    "oracle": rerun_oracle,
    "analysis": rerun_analysis,
}
