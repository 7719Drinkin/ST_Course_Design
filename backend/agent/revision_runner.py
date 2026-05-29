from __future__ import annotations

from typing import Any

from .pipeline.agent_pipeline import AgentPipeline
from .prompts.prompt_builder import PromptBuilder
from .revision.revision_impact import (
    has_revision_scope,
    impacted_coverage_items,
    impacted_test_cases,
    related_requirements,
    related_risk_results,
    related_strategies,
    revision_impact,
    workflow_state,
)
from .revision.revision_reentry import ReentryContext, rerun_from_impact
from .revision.revision_utils import RevisionRunnerError, dedupe, make_next_id, merge_grouped, prompt_evidence, renumber_evidence, string_list
from .tools.clients.llm_client import LLMClient


async def regenerate_from_revision(
    revision: dict[str, Any],
    current_state: dict[str, Any],
    rag_context: str | None = None,
) -> dict[str, Any]:
    """Run a scoped AgentPipeline rerun for one designer revision."""

    if not revision:
        raise RevisionRunnerError("revision is required", 422)

    state = workflow_state(current_state)
    created, updated, unchanged, deprecated = revision_impact(revision, state)
    generated_created, generated_updated, generated_deprecated, prompt_evidence_items = await _regenerate_impacted_items(
        revision,
        state,
        updated,
        deprecated,
        current_state,
        rag_context,
    )
    merge_grouped(created, generated_created)
    merge_grouped(updated, generated_updated)
    merge_grouped(deprecated, generated_deprecated)

    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "deprecated": deprecated,
        "prompt_evidence": renumber_evidence(prompt_evidence_items),
    }


async def _regenerate_impacted_items(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    updated: dict[str, Any],
    deprecated: dict[str, Any],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    impacted_coverage = impacted_coverage_items(revision, state, updated)
    impacted_tests = impacted_test_cases(state, updated, deprecated, impacted_coverage)
    if not has_revision_scope(revision, state, impacted_coverage, impacted_tests):
        raise RevisionRunnerError(
            "revision does not affect a known requirement, coverage item, strategy, test case, or oracle result",
            422,
        )

    impact, prompt_evidence_items = await _llm_revision_impact(
        revision,
        state,
        impacted_coverage,
        impacted_tests,
        current_state,
        rag_context,
    )
    try:
        reentry_result = await rerun_from_impact(
            ReentryContext(
                revision=revision,
                state=state,
                impact=impact,
                impacted_coverage=impacted_coverage,
                impacted_tests=impacted_tests,
                current_state=current_state,
                rag_context=rag_context,
                pipeline=AgentPipeline(),
            )
        )
    except RevisionRunnerError:
        raise
    except Exception as exc:
        raise RevisionRunnerError(f"AgentPipeline revision rerun failed: {exc}", 503) from exc

    return (
        reentry_result.changes.created,
        reentry_result.changes.updated,
        reentry_result.changes.deprecated,
        [*prompt_evidence_items, *reentry_result.evidence],
    )


async def _llm_revision_impact(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prompt_input = _revision_regenerate_prompt_input(
        revision,
        state,
        impacted_coverage,
        impacted_tests,
        current_state,
        rag_context,
    )
    prompt = PromptBuilder().build("revision_regenerate", prompt_input)
    try:
        payload = await LLMClient().generate_json(prompt)
    except Exception as exc:
        raise RevisionRunnerError(f"LLM revision impact analysis failed: {exc}", 503) from exc

    impact = _normalize_revision_impact(payload, revision, impacted_coverage, impacted_tests)
    evidence_items = _revision_regenerate_evidence(
        str(revision.get("session_id") or ""),
        str(revision.get("revision_id") or ""),
        prompt,
        prompt_input,
        impact,
    )
    return impact, evidence_items


def _revision_regenerate_prompt_input(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> dict[str, Any]:
    return {
        "session_id": str(revision.get("session_id") or ""),
        "revision": revision,
        "related_requirements": related_requirements(state, revision, impacted_coverage, impacted_tests),
        "related_risk_results": related_risk_results(state, impacted_coverage, impacted_tests),
        "impacted_coverage_items": impacted_coverage,
        "impacted_strategies": related_strategies(state, impacted_coverage, impacted_tests),
        "impacted_test_cases": impacted_tests,
        "next_test_id_hint": make_next_id("TC-AUT", state.get("test_cases", []), "test_id"),
        "rag_context": rag_context or str((current_state or {}).get("rag_context") or ""),
    }


def _normalize_revision_impact(
    payload: dict[str, Any],
    revision: dict[str, Any],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RevisionRunnerError("LLM revision impact output must be a JSON object", 502)

    reentry_stage = str(payload.get("reentry_stage") or "").strip()
    allowed = {"parse", "risk", "strategy", "generate", "fsm", "oracle", "analysis"}
    if reentry_stage not in allowed:
        raise RevisionRunnerError(f"invalid LLM reentry_stage: {reentry_stage or '<empty>'}", 502)

    affected_ids = payload.get("affected_ids") if isinstance(payload.get("affected_ids"), dict) else {}
    normalized_affected = {
        "requirements": string_list(affected_ids.get("requirements")),
        "risk_results": string_list(affected_ids.get("risk_results")),
        "coverage_items": string_list(affected_ids.get("coverage_items")),
        "strategies": string_list(affected_ids.get("strategies")),
        "test_cases": string_list(affected_ids.get("test_cases")),
        "oracle_results": string_list(affected_ids.get("oracle_results")),
    }
    if not normalized_affected["coverage_items"]:
        normalized_affected["coverage_items"] = [
            str(item.get("coverage_item_id"))
            for item in impacted_coverage
            if item.get("coverage_item_id")
        ]
    if not normalized_affected["test_cases"]:
        normalized_affected["test_cases"] = [
            str(item.get("test_id"))
            for item in impacted_tests
            if item.get("test_id")
        ]
    if not normalized_affected["requirements"]:
        normalized_affected["requirements"] = dedupe(
            [
                str(item.get("requirement_id"))
                for item in [*impacted_coverage, *impacted_tests]
                if item.get("requirement_id")
            ]
        )
    if not normalized_affected["oracle_results"] and revision.get("target_type") in {"oracle", "oracle_result"}:
        normalized_affected["oracle_results"] = [str(revision.get("target_id") or "")]

    return {
        "impact_analysis": payload.get("impact_analysis") if isinstance(payload.get("impact_analysis"), list) else [],
        "reentry_stage": reentry_stage,
        "affected_ids": normalized_affected,
        "rationale": str(payload.get("rationale") or ""),
        "warnings": string_list(payload.get("warnings")),
        "revision_id": revision.get("revision_id"),
    }


def _revision_regenerate_evidence(
    session_id: str,
    revision_id: str,
    prompt: str,
    prompt_input: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        prompt_evidence(
            session_id,
            "revision_regenerate",
            revision_id,
            {**prompt_input, "prompt": prompt},
            {
                "impact_analysis": payload.get("impact_analysis", []),
                "reentry_stage": payload.get("reentry_stage", ""),
                "affected_ids": payload.get("affected_ids", {}),
                "rationale": payload.get("rationale", ""),
                "warnings": payload.get("warnings", []),
            },
            "LLM-based revision impact interpretation for scoped AgentPipeline rerun.",
        )
    ]


__all__ = ["RevisionRunnerError", "regenerate_from_revision"]
