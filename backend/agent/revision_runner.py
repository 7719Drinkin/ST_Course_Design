from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .pipeline.agent_pipeline import AgentPipeline
from .prompts.prompt_builder import PromptBuilder
from .tools.clients.llm_client import LLMClient


TARGET_TO_COLLECTION = {
    "requirement": ("requirements", "requirement_id"),
    "parsed_requirement": ("parsed_requirements", "requirement_id"),
    "risk_result": ("risk_results", "target_id"),
    "coverage_item": ("coverage_items", "coverage_item_id"),
    "strategy": ("strategies", "strategy_id"),
    "test_case": ("test_cases", "test_id"),
    "oracle": ("oracle_results", "test_id"),
    "oracle_result": ("oracle_results", "test_id"),
}

STATE_LIST_KEYS = (
    "requirements",
    "parsed_requirements",
    "risk_results",
    "coverage_goals",
    "coverage_items",
    "strategies",
    "test_design_specs",
    "test_cases",
    "oracle_results",
    "prompt_evidence",
)


class RevisionRunnerError(RuntimeError):
    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


async def regenerate_from_revision(
    revision: dict[str, Any],
    current_state: dict[str, Any],
    rag_context: str | None = None,
) -> dict[str, Any]:
    """Run a scoped AgentPipeline rerun for one designer revision.

    This is the agent-layer public entrypoint for 3.10. It does not reuse the
    first-run full requirement runner because revision input is structured
    design state, not raw requirement text.
    """

    if not revision:
        raise RevisionRunnerError("revision is required", 422)
    state = _workflow_state(current_state)
    created, updated, unchanged, deprecated = _revision_impact(revision, state)
    generated_created, generated_updated, generated_deprecated, prompt_evidence = await _regenerate_impacted_items(
        revision,
        state,
        updated,
        deprecated,
        current_state,
        rag_context,
    )
    _merge_grouped(created, generated_created)
    _merge_grouped(updated, generated_updated)
    _merge_grouped(deprecated, generated_deprecated)

    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "deprecated": deprecated,
        "prompt_evidence": _renumber_evidence(prompt_evidence),
    }


async def _regenerate_impacted_items(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    updated: dict[str, Any],
    deprecated: dict[str, Any],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    impacted_coverage = _impacted_coverage_items(revision, state, updated)
    impacted_tests = _impacted_test_cases(state, updated, deprecated, impacted_coverage)
    if not _has_revision_scope(revision, state, impacted_coverage, impacted_tests):
        raise RevisionRunnerError(
            "revision does not affect a known requirement, coverage item, strategy, test case, or oracle result",
            422,
        )

    impact, prompt_evidence = await _llm_revision_impact(
        revision,
        state,
        impacted_coverage,
        impacted_tests,
        current_state,
        rag_context,
    )
    try:
        created, regenerated, deprecated_items, pipeline_evidence = await _rerun_pipeline_from_impact(
            impact,
            revision,
            state,
            impacted_coverage,
            impacted_tests,
            current_state,
            rag_context,
        )
    except RevisionRunnerError:
        raise
    except Exception as exc:
        raise RevisionRunnerError(f"AgentPipeline revision rerun failed: {exc}", 503) from exc
    return created, regenerated, deprecated_items, [*prompt_evidence, *pipeline_evidence]


def _workflow_state(current_state: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    state = current_state or {}
    return {
        key: _to_dicts(state.get(key))
        for key in STATE_LIST_KEYS
    }


def _revision_impact(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    target_type = str(revision.get("target_type") or "")
    target_id = str(revision.get("target_id") or "")
    after = revision.get("after") if isinstance(revision.get("after"), dict) else {}
    before = revision.get("before") if isinstance(revision.get("before"), dict) else {}
    target_collection = TARGET_TO_COLLECTION.get(target_type)

    affected = _affected_ids(target_type, target_id, state)
    updated: dict[str, Any] = {}
    unchanged: dict[str, Any] = {}
    created: dict[str, Any] = {}
    deprecated: dict[str, Any] = {}

    for collection, items in state.items():
        id_field = _collection_id_field(collection)
        if not id_field:
            continue
        affected_ids = affected.get(collection, set())
        selected = [item for item in items if str(item.get(id_field) or "") in affected_ids]
        rest = [item for item in items if str(item.get(id_field) or "") not in affected_ids]
        if target_collection and collection == target_collection[0]:
            selected = [
                _merge_revision_patch(item, target_id, id_field, after)
                for item in selected
            ]
        if selected:
            updated[collection] = selected
        if rest:
            unchanged[collection] = rest

    if target_collection and not before:
        collection, id_field = target_collection
        created[collection] = [{**after, id_field: target_id}]
        updated.pop(collection, None)

    if _is_deprecated(after):
        if target_collection:
            collection, _ = target_collection
            deprecated[collection] = updated.pop(collection, [after])
        related_tests = updated.get("test_cases", [])
        if related_tests:
            deprecated["test_cases"] = related_tests
            updated.pop("test_cases", None)

    if not any((created, updated, unchanged, deprecated)):
        updated[target_type or "unknown"] = [after or revision]

    return created, updated, unchanged, deprecated


def _merge_revision_patch(
    item: dict[str, Any],
    target_id: str,
    id_field: str,
    after: dict[str, Any],
) -> dict[str, Any]:
    if str(item.get(id_field) or "") != target_id:
        return item
    revised = dict(item)
    revised.update(after)
    revised.setdefault(id_field, target_id)
    return revised


def _has_revision_scope(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> bool:
    target_type = str(revision.get("target_type") or "")
    target_id = str(revision.get("target_id") or "")
    if impacted_coverage or impacted_tests:
        return True
    if target_type in {"requirement", "parsed_requirement"}:
        return any(
            str(item.get("requirement_id") or "") == target_id
            for item in [*state.get("requirements", []), *state.get("parsed_requirements", [])]
        )
    if target_type == "risk_result":
        return any(
            str(item.get("requirement_id") or item.get("target_id") or "") == target_id
            for item in state.get("risk_results", [])
        )
    if target_type in {"oracle", "oracle_result"}:
        return any(
            str(item.get("test_id") or item.get("oracle_id") or "") == target_id
            for item in state.get("oracle_results", [])
        )
    return False


def _impacted_coverage_items(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    updated: dict[str, Any],
) -> list[dict[str, Any]]:
    if updated.get("coverage_items"):
        return list(updated["coverage_items"])
    target_type = str(revision.get("target_type") or "")
    target_id = str(revision.get("target_id") or "")
    if target_type == "strategy":
        coverage_ids = {
            str(item.get("coverage_item_id"))
            for item in state.get("strategies", [])
            if item.get("strategy_id") == target_id and item.get("coverage_item_id")
        }
        return [
            item for item in state.get("coverage_items", [])
            if str(item.get("coverage_item_id") or "") in coverage_ids
        ]
    if target_type == "risk_result":
        return [
            item for item in state.get("coverage_items", [])
            if item.get("requirement_id") == target_id or item.get("coverage_item_id") == target_id
        ]
    return []


def _impacted_test_cases(
    state: dict[str, list[dict[str, Any]]],
    updated: dict[str, Any],
    deprecated: dict[str, Any],
    impacted_coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected.extend(item for item in updated.get("test_cases", []) if isinstance(item, dict))
    selected.extend(item for item in deprecated.get("test_cases", []) if isinstance(item, dict))
    coverage_ids = {
        str(item.get("coverage_item_id") or "")
        for item in impacted_coverage
        if item.get("coverage_item_id")
    }
    selected.extend(
        item
        for item in state.get("test_cases", [])
        if _test_case_coverage_ids(item) & coverage_ids
    )
    return _dedupe_by_id(selected, "test_id")


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
    prompt_evidence = _revision_regenerate_evidence(
        str(revision.get("session_id") or ""),
        str(revision.get("revision_id") or ""),
        prompt,
        prompt_input,
        impact,
    )
    return impact, prompt_evidence


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
        "related_requirements": _related_requirements(state, revision, impacted_coverage, impacted_tests),
        "related_risk_results": _related_risk_results(state, impacted_coverage, impacted_tests),
        "impacted_coverage_items": impacted_coverage,
        "impacted_strategies": _related_strategies(state, impacted_coverage, impacted_tests),
        "impacted_test_cases": impacted_tests,
        "next_test_id_hint": _make_next_id("TC-AUT", state.get("test_cases", []), "test_id"),
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
        "requirements": _string_list(affected_ids.get("requirements")),
        "risk_results": _string_list(affected_ids.get("risk_results")),
        "coverage_items": _string_list(affected_ids.get("coverage_items")),
        "strategies": _string_list(affected_ids.get("strategies")),
        "test_cases": _string_list(affected_ids.get("test_cases")),
        "oracle_results": _string_list(affected_ids.get("oracle_results")),
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
        normalized_affected["requirements"] = _dedupe(
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
        "warnings": _string_list(payload.get("warnings")),
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
        _prompt_evidence(
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


async def _rerun_pipeline_from_impact(
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    stage = str(impact.get("reentry_stage") or "")
    if stage == "analysis":
        return {}, {}, {}, []
    if stage == "oracle":
        return await _rerun_from_oracle(impact, revision, state, impacted_tests, current_state, rag_context)
    if stage == "fsm":
        return await _rerun_from_fsm(impact, revision, state, impacted_coverage, impacted_tests, current_state, rag_context)
    if stage == "generate":
        return await _rerun_from_generate(impact, revision, state, impacted_coverage, impacted_tests, current_state, rag_context)
    if stage == "strategy":
        return await _rerun_from_strategy(impact, revision, state, impacted_coverage, impacted_tests, current_state, rag_context)
    if stage == "risk":
        return await _rerun_from_risk(impact, revision, state, impacted_tests, current_state, rag_context)
    if stage == "parse":
        return await _rerun_from_parse(impact, revision, state, current_state, rag_context)
    raise RevisionRunnerError(f"unsupported reentry_stage: {stage}", 502)


async def _rerun_from_generate(
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    coverage_items = _selected_coverage_items(impact, state, impacted_coverage)
    ep_bva_dt = [_agent_coverage_item(item, state) for item in coverage_items if _coverage_technique(item) != "FSM"]
    fsm_items = [item for item in coverage_items if _coverage_technique(item) == "FSM"]

    created: dict[str, Any] = {}
    updated: dict[str, Any] = {}
    deprecated: dict[str, Any] = {}
    evidence_items: list[dict[str, Any]] = []

    if ep_bva_dt:
        result = await AgentPipeline().generate_tests(
            ep_bva_dt,
            _agent_risk_items(state, coverage_items),
            rag_context or _rag_context(current_state),
        )
        generated_tests = _model_dump_list(result.test_cases)
        _mark_revision(generated_tests, revision, "pipeline_regenerated")
        created_tests, updated_tests = _split_created_updated(generated_tests, state.get("test_cases", []), "test_id")
        _add_group(created, "test_cases", created_tests)
        _add_group(updated, "test_cases", updated_tests)
        evidence_items.extend(
            _agent_prompt_records_to_evidence(
                str(revision.get("session_id") or ""),
                result.prompts_used,
                str(revision.get("revision_id") or ""),
                {"stage": "generate", "test_case_count": len(generated_tests)},
                "Revision re-entered AgentPipeline.generate_tests.",
            )
        )

    if fsm_items:
        fsm_created, fsm_updated, fsm_deprecated, fsm_evidence = await _rerun_from_fsm(
            impact,
            revision,
            state,
            fsm_items,
            impacted_tests,
            current_state,
            rag_context,
        )
        _merge_grouped(created, fsm_created)
        _merge_grouped(updated, fsm_updated)
        _merge_grouped(deprecated, fsm_deprecated)
        evidence_items.extend(fsm_evidence)

    _deprecate_replaced_tests(deprecated, impacted_tests, created, updated, revision)
    return created, updated, deprecated, evidence_items


async def _rerun_from_fsm(
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    coverage_items = impacted_coverage or _selected_coverage_items(impact, state, [])
    result = await AgentPipeline().generate_fsm(
        requirements=_related_requirements(state, revision, coverage_items, impacted_tests),
        parsed_requirements=state.get("parsed_requirements", []),
        coverage_items=coverage_items,
        rag_context=rag_context or _rag_context(current_state),
    )
    fsm_payload = result.fsm.model_dump(mode="json", by_alias=True)
    generated_tests = _model_dump_list(result.test_cases)
    _mark_revision(generated_tests, revision, "pipeline_regenerated")
    created_tests, updated_tests = _split_created_updated(generated_tests, state.get("test_cases", []), "test_id")

    created = {"test_cases": created_tests} if created_tests else {}
    updated: dict[str, Any] = {"fsm": fsm_payload}
    if updated_tests:
        updated["test_cases"] = updated_tests
    deprecated: dict[str, Any] = {}
    _deprecate_replaced_tests(deprecated, impacted_tests, created, updated, revision)
    evidence_items = _agent_prompt_records_to_evidence(
        str(revision.get("session_id") or ""),
        result.prompts_used,
        str(revision.get("revision_id") or ""),
        {"stage": "fsm", "test_case_count": len(generated_tests)},
        "Revision re-entered AgentPipeline.generate_fsm.",
    )
    return created, updated, deprecated, evidence_items


async def _rerun_from_oracle(
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    test_cases = impacted_tests or _selected_test_cases(impact, state)
    if not test_cases:
        raise RevisionRunnerError("oracle reentry requires at least one affected test case", 422)
    result = await AgentPipeline().generate_oracles(
        test_cases,
        requirements=_related_requirements(state, revision, [], test_cases),
        rag_context=rag_context or _rag_context(current_state),
    )
    oracle_results = _model_dump_list(result.oracle_results)
    _mark_revision(oracle_results, revision, "pipeline_regenerated")
    updated = {"oracle_results": oracle_results} if oracle_results else {}
    evidence_items = _agent_prompt_records_to_evidence(
        str(revision.get("session_id") or ""),
        result.prompts_used,
        str(revision.get("revision_id") or ""),
        {"stage": "oracle", "oracle_result_count": len(oracle_results)},
        "Revision re-entered AgentPipeline.generate_oracles.",
    )
    return {}, updated, {}, evidence_items


async def _rerun_from_strategy(
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    coverage_items = _selected_coverage_items(impact, state, impacted_coverage)
    if not coverage_items:
        raise RevisionRunnerError("strategy reentry requires affected coverage items", 422)
    strategy_result = await AgentPipeline().assign_strategy(
        _coverage_goals_from_coverage_items(coverage_items),
        _analyzed_requirements_for_items(state, coverage_items),
        _agent_risk_items(state, coverage_items),
        rag_context or _rag_context(current_state),
    )
    new_coverage = _model_dump_list(strategy_result.coverage_items)
    _mark_revision(new_coverage, revision, "pipeline_regenerated")

    generate_created, generate_updated, generate_deprecated, generate_evidence = await _rerun_from_generate(
        {**impact, "affected_ids": {**impact.get("affected_ids", {}), "coverage_items": [item.get("coverage_item_id") for item in new_coverage]}},
        revision,
        {**state, "coverage_items": _merge_items(state.get("coverage_items", []), new_coverage, "coverage_item_id")},
        new_coverage,
        impacted_tests,
        current_state,
        rag_context,
    )
    _add_group(generate_updated, "coverage_items", new_coverage)
    evidence_items = _agent_prompt_records_to_evidence(
        str(revision.get("session_id") or ""),
        strategy_result.prompts_used,
        str(revision.get("revision_id") or ""),
        {"stage": "strategy", "coverage_item_count": len(new_coverage)},
        "Revision re-entered AgentPipeline.assign_strategy.",
    )
    return generate_created, generate_updated, generate_deprecated, [*evidence_items, *generate_evidence]


async def _rerun_from_risk(
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    requirements = _analyzed_requirements_for_items(
        state,
        _selected_requirements(impact, state),
    )
    if not requirements:
        raise RevisionRunnerError("risk reentry requires affected analyzed requirements", 422)
    risk_result = await AgentPipeline().analyze_risk(requirements, rag_context or _rag_context(current_state))
    risk_items = _model_dump_list(risk_result.risk_analysis)

    strategy_created, strategy_updated, strategy_deprecated, strategy_evidence = await _rerun_from_strategy(
        impact,
        revision,
        {**state, "risk_results": _merge_items(state.get("risk_results", []), risk_items, "requirement_id")},
        _selected_coverage_items(impact, state, []),
        impacted_tests,
        current_state,
        rag_context,
    )
    _add_group(strategy_updated, "risk_results", risk_items)
    evidence_items = _agent_prompt_records_to_evidence(
        str(revision.get("session_id") or ""),
        risk_result.prompts_used,
        str(revision.get("revision_id") or ""),
        {"stage": "risk", "risk_count": len(risk_items)},
        "Revision re-entered AgentPipeline.analyze_risk.",
    )
    return strategy_created, strategy_updated, strategy_deprecated, [*evidence_items, *strategy_evidence]


async def _rerun_from_parse(
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    current_state: dict[str, Any] | None,
    rag_context: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    requirement_text = _revision_requirement_text(revision, state)
    if not requirement_text:
        raise RevisionRunnerError("parse reentry requires revised requirement text", 422)
    pipeline = AgentPipeline()
    parse_result = await pipeline.parse_requirements(requirement_text, rag_context or _rag_context(current_state))
    parsed_requirements = _model_dump_list(parse_result.requirements)
    analyzed_requirements = _model_dump_list(parse_result.analyzed_requirements)

    risk_result = await pipeline.analyze_risk(parse_result.analyzed_requirements, rag_context or _rag_context(current_state))
    risk_items = _model_dump_list(risk_result.risk_analysis)

    coverage_result = await pipeline.identify_coverage(
        parse_result.analyzed_requirements,
        risk_result.risk_analysis,
        rag_context or _rag_context(current_state),
    )
    strategy_result = await pipeline.assign_strategy(
        coverage_result.coverage_goals,
        parse_result.analyzed_requirements,
        risk_result.risk_analysis,
        rag_context or _rag_context(current_state),
    )
    coverage_items = _model_dump_list(strategy_result.coverage_items)

    generate_result = await pipeline.generate_tests(
        strategy_result.coverage_items,
        risk_result.risk_analysis,
        rag_context or _rag_context(current_state),
    )
    test_cases = _model_dump_list(generate_result.test_cases)
    _mark_revision(test_cases, revision, "pipeline_regenerated")

    updated = {
        "parsed_requirements": parsed_requirements,
        "requirements": analyzed_requirements,
        "risk_results": risk_items,
        "coverage_items": coverage_items,
        "test_cases": test_cases,
    }
    evidence_items: list[dict[str, Any]] = []
    for records, stage, count_key, count in [
        (parse_result.prompts_used, "parse", "parsed_requirement_count", len(parsed_requirements)),
        (risk_result.prompts_used, "risk", "risk_count", len(risk_items)),
        (coverage_result.prompts_used, "coverage", "coverage_goal_count", len(coverage_result.coverage_goals)),
        (strategy_result.prompts_used, "strategy", "coverage_item_count", len(coverage_items)),
        (generate_result.prompts_used, "generate", "test_case_count", len(test_cases)),
    ]:
        evidence_items.extend(
            _agent_prompt_records_to_evidence(
                str(revision.get("session_id") or ""),
                records,
                str(revision.get("revision_id") or ""),
                {"stage": stage, count_key: count},
                f"Revision re-entered AgentPipeline.{stage}.",
            )
        )
    return {}, updated, {}, evidence_items


def _related_requirements(
    state: dict[str, list[dict[str, Any]]],
    revision: dict[str, Any],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirement_ids = {
        str(revision.get("target_id") or "")
        if revision.get("target_type") in {"requirement", "parsed_requirement"}
        else ""
    }
    requirement_ids.update(
        str(item.get("requirement_id"))
        for item in [*impacted_coverage, *impacted_tests]
        if item.get("requirement_id")
    )
    result = [
        item
        for item in [*state.get("requirements", []), *state.get("parsed_requirements", [])]
        if str(item.get("requirement_id") or "") in requirement_ids
    ]
    return _dedupe_by_id(result, "requirement_id")


def _related_risk_results(
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirement_ids = {
        str(item.get("requirement_id"))
        for item in [*impacted_coverage, *impacted_tests]
        if item.get("requirement_id")
    }
    coverage_ids = {
        str(item.get("coverage_item_id"))
        for item in impacted_coverage
        if item.get("coverage_item_id")
    }
    return [
        item
        for item in state.get("risk_results", [])
        if str(item.get("requirement_id") or item.get("target_id") or "") in requirement_ids | coverage_ids
    ]


def _related_strategies(
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage_ids = {
        str(item.get("coverage_item_id"))
        for item in impacted_coverage
        if item.get("coverage_item_id")
    }
    coverage_ids.update(
        str(item.get("coverage_item_id"))
        for item in impacted_tests
        if item.get("coverage_item_id")
    )
    strategy_ids = {
        str(item.get("strategy_id"))
        for item in impacted_tests
        if item.get("strategy_id")
    }
    return [
        item
        for item in state.get("strategies", [])
        if str(item.get("coverage_item_id") or "") in coverage_ids
        or str(item.get("strategy_id") or "") in strategy_ids
    ]


def _affected_ids(
    target_type: str,
    target_id: str,
    state: dict[str, list[dict[str, Any]]],
) -> dict[str, set[str]]:
    affected: dict[str, set[str]] = {key: set() for key in state}
    if target_type in {"requirement", "parsed_requirement"}:
        affected["requirements"].add(target_id)
        affected["parsed_requirements"].add(target_id)
        coverage_ids = {
            str(item.get("coverage_item_id"))
            for item in state["coverage_items"]
            if item.get("requirement_id") == target_id and item.get("coverage_item_id")
        }
        affected["coverage_items"].update(coverage_ids)
        affected["risk_results"].add(target_id)
        _mark_related_by_coverage(affected, coverage_ids, state)
        affected["test_cases"].update(
            str(item.get("test_id"))
            for item in state["test_cases"]
            if item.get("requirement_id") == target_id and item.get("test_id")
        )
    elif target_type == "risk_result":
        affected["risk_results"].add(target_id)
        affected["test_cases"].update(
            str(item.get("test_id"))
            for item in state["test_cases"]
            if item.get("requirement_id") == target_id or item.get("coverage_item_id") == target_id
        )
    elif target_type == "coverage_item":
        coverage_ids = {target_id}
        affected["coverage_items"].add(target_id)
        _mark_related_by_coverage(affected, coverage_ids, state)
    elif target_type == "strategy":
        affected["strategies"].add(target_id)
        coverage_ids = {
            str(item.get("coverage_item_id"))
            for item in state["strategies"]
            if item.get("strategy_id") == target_id and item.get("coverage_item_id")
        }
        _mark_related_by_coverage(affected, coverage_ids, state)
        affected["test_cases"].update(
            str(item.get("test_id"))
            for item in state["test_cases"]
            if item.get("strategy_id") == target_id and item.get("test_id")
        )
    elif target_type == "test_case":
        affected["test_cases"].add(target_id)
        affected["oracle_results"].add(target_id)
    elif target_type in {"oracle", "oracle_result"}:
        affected["oracle_results"].add(target_id)
        affected["test_cases"].add(target_id)
    return affected


def _mark_related_by_coverage(
    affected: dict[str, set[str]],
    coverage_ids: set[str],
    state: dict[str, list[dict[str, Any]]],
) -> None:
    affected["strategies"].update(
        str(item.get("strategy_id"))
        for item in state["strategies"]
        if item.get("coverage_item_id") in coverage_ids and item.get("strategy_id")
    )
    affected["test_cases"].update(
        str(item.get("test_id"))
        for item in state["test_cases"]
        if item.get("coverage_item_id") in coverage_ids and item.get("test_id")
    )
    affected["risk_results"].update(coverage_ids)


def _collection_id_field(collection: str) -> str | None:
    return {
        "requirements": "requirement_id",
        "parsed_requirements": "requirement_id",
        "risk_results": "target_id",
        "coverage_goals": "coverage_goal_id",
        "coverage_items": "coverage_item_id",
        "strategies": "strategy_id",
        "test_design_specs": "spec_id",
        "test_cases": "test_id",
        "oracle_results": "test_id",
    }.get(collection)


def _test_case_coverage_ids(test_case: dict[str, Any]) -> set[str]:
    values = {
        str(test_case.get("coverage_item_id") or ""),
        *[str(item) for item in test_case.get("coverage_item_ids", []) if item],
    }
    return {item for item in values if item}


def _selected_coverage_items(
    impact: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = set(_string_list((impact.get("affected_ids") or {}).get("coverage_items")))
    if not ids:
        return fallback
    return [item for item in state.get("coverage_items", []) if str(item.get("coverage_item_id") or "") in ids]


def _selected_test_cases(
    impact: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ids = set(_string_list((impact.get("affected_ids") or {}).get("test_cases")))
    return [item for item in state.get("test_cases", []) if str(item.get("test_id") or "") in ids]


def _selected_requirements(
    impact: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ids = set(_string_list((impact.get("affected_ids") or {}).get("requirements")))
    if not ids:
        return state.get("parsed_requirements", []) or state.get("requirements", [])
    return [
        item
        for item in [*state.get("parsed_requirements", []), *state.get("requirements", [])]
        if str(item.get("requirement_id") or "") in ids
    ]


def _agent_coverage_item(item: dict[str, Any], state: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    coverage_id = str(item.get("coverage_item_id") or "")
    strategy = _strategy_for_coverage(state, coverage_id)
    technique = _coverage_technique(item)
    return {
        "coverage_item_id": coverage_id,
        "coverage_goal_id": str(item.get("coverage_goal_id") or coverage_id),
        "requirement_id": str(item.get("requirement_id") or ""),
        "technique": technique if technique in {"EP", "BVA", "DT"} else "EP",
        "description": str(item.get("description") or item.get("goal") or "Regenerate revised coverage item"),
        "conditions": _string_list(item.get("conditions") or item.get("related_conditions")),
        "data_ranges": _string_list(item.get("data_ranges")),
        "input_fields": _string_list(item.get("input_fields") or item.get("related_inputs")),
        "expected_action": str(item.get("expected_action") or ""),
        "strategy_rationale": str(item.get("strategy_rationale") or strategy.get("reason") or "Designer revision requires downstream regeneration."),
        "technique_reason": str(item.get("technique_reason") or strategy.get("reason") or "Technique retained from revised coverage item."),
    }


def _strategy_for_coverage(state: dict[str, list[dict[str, Any]]], coverage_id: str) -> dict[str, Any]:
    for strategy in state.get("strategies", []):
        if str(strategy.get("coverage_item_id") or "") == coverage_id:
            return strategy
    return {}


def _agent_risk_items(
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
        impact = _bounded_int(item.get("impact"), 3)
        likelihood = _bounded_int(item.get("likelihood"), 3)
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
                "risk_reason": str(item.get("risk_reason") or item.get("reason") or "Risk inherited from current state."),
            }
        )
    return result


def _analyzed_requirements_for_items(
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
                "input_fields": _string_list(item.get("input_fields") or item.get("related_inputs")),
                "data_ranges": _string_list(item.get("data_ranges")),
                "conditions": _string_list(item.get("conditions") or item.get("related_conditions")),
                "business_rules": _string_list(item.get("business_rules")),
                "expected_action": str(item.get("expected_action") or ""),
            }
        )
    return _dedupe_by_id(analyzed, "requirement_id")


def _coverage_goals_from_coverage_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "coverage_goal_id": str(item.get("coverage_goal_id") or item.get("coverage_item_id") or ""),
            "requirement_id": str(item.get("requirement_id") or ""),
            "goal": str(item.get("description") or item.get("expected_action") or "Regenerate revised coverage goal"),
            "related_inputs": _string_list(item.get("input_fields") or item.get("related_inputs")),
            "related_conditions": _string_list(item.get("conditions") or item.get("related_conditions")),
            "expected_action": str(item.get("expected_action") or ""),
        }
        for item in items
    ]


def _merge_items(existing: list[dict[str, Any]], updates: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    by_id = {str(item.get(id_field) or ""): dict(item) for item in existing}
    for item in updates:
        item_id = str(item.get(id_field) or "")
        if item_id:
            by_id[item_id] = item
    return [item for item in by_id.values() if item]


def _mark_revision(items: list[dict[str, Any]], revision: dict[str, Any], status: str) -> None:
    for item in items:
        item["revision_status"] = status
        item["regenerated_from_revision"] = revision.get("revision_id")


def _split_created_updated(
    generated: list[dict[str, Any]],
    existing: list[dict[str, Any]],
    id_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    existing_ids = {str(item.get(id_field) or "") for item in existing}
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    for item in generated:
        if str(item.get(id_field) or "") in existing_ids:
            updated.append(item)
        else:
            created.append(item)
    return created, updated


def _add_group(target: dict[str, Any], key: str, values: list[dict[str, Any]]) -> None:
    if values:
        target.setdefault(key, [])
        target[key].extend(values)


def _deprecate_replaced_tests(
    deprecated: dict[str, Any],
    impacted_tests: list[dict[str, Any]],
    created: dict[str, Any],
    updated: dict[str, Any],
    revision: dict[str, Any],
) -> None:
    new_ids = {
        str(item.get("test_id") or "")
        for item in [*created.get("test_cases", []), *updated.get("test_cases", [])]
        if item.get("test_id")
    }
    replacements: list[dict[str, Any]] = []
    for item in impacted_tests:
        test_id = str(item.get("test_id") or "")
        if not test_id or test_id in new_ids:
            continue
        replacements.append(
            {
                **item,
                "status": "Rejected",
                "review_status": "deprecated_by_revision",
                "deprecated_by_revision": revision.get("revision_id"),
            }
        )
    _add_group(deprecated, "test_cases", replacements)


def _agent_prompt_records_to_evidence(
    session_id: str,
    records: list[Any],
    target_id: str,
    output_summary: dict[str, Any],
    note: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        item = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
        result.append(
            _prompt_evidence(
                session_id,
                str(item.get("name") or item.get("prompt_name") or "agent_pipeline"),
                target_id,
                {"prompt": item.get("prompt", ""), **dict(item.get("input") or {})},
                output_summary,
                note,
            )
        )
    return result


def _revision_requirement_text(revision: dict[str, Any], state: dict[str, list[dict[str, Any]]]) -> str:
    after = revision.get("after") if isinstance(revision.get("after"), dict) else {}
    for key in ("text", "raw_text", "description", "content", "title"):
        if after.get(key):
            return str(after[key])
    target_id = str(revision.get("target_id") or "")
    for item in [*state.get("requirements", []), *state.get("parsed_requirements", [])]:
        if str(item.get("requirement_id") or "") != target_id:
            continue
        for key in ("text", "raw_text", "description", "content", "title"):
            if item.get(key):
                return str(item[key])
    return ""


def _merge_grouped(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, values in source.items():
        if not values:
            continue
        if not isinstance(values, list):
            target[key] = values
            continue
        target.setdefault(key, [])
        id_field = _collection_id_field(key) or "id"
        existing_ids = {
            str(item.get(id_field) or "")
            for item in target[key]
            if isinstance(item, dict)
        }
        for item in values:
            item_id = str(item.get(id_field) or "") if isinstance(item, dict) else ""
            if item_id and item_id in existing_ids:
                target[key] = [
                    item if str(existing.get(id_field) or "") == item_id else existing
                    for existing in target[key]
                ]
            else:
                target[key].append(item)


def _prompt_evidence(
    session_id: str,
    prompt_name: str,
    target_id: str,
    prompt_input: dict[str, Any],
    output: dict[str, Any],
    note: str,
) -> dict[str, Any]:
    return {
        "evidence_id": "",
        "session_id": session_id,
        "prompt_name": prompt_name,
        "target_id": target_id,
        "input": prompt_input,
        "output": output,
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _renumber_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        result.append({**item, "evidence_id": f"PE-AUT-{index:03d}"})
    return result


def _model_dump_list(items: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        result.append(item.model_dump(mode="json", by_alias=True) if hasattr(item, "model_dump") else dict(item))
    return result


def _to_dicts(items: Any) -> list[dict[str, Any]]:
    if items is None:
        return []
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump(mode="json", by_alias=True))
        elif isinstance(item, dict):
            result.append(dict(item))
    return result


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple | set):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _dedupe_by_id(items: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get(id_field) or "")
        key = item_id or repr(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _coverage_technique(item: dict[str, Any]) -> str:
    technique = str(item.get("technique") or item.get("strategy") or "").upper()
    if technique in {"EP", "BVA", "DT", "FSM"}:
        return technique
    return "EP"


def _rag_context(current_state: dict[str, Any] | None) -> str:
    return str((current_state or {}).get("rag_context") or "")


def _bounded_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(5, parsed))


def _is_deprecated(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or item.get("review_status") or "").lower()
    return status in {"rejected", "deprecated"}


def _make_next_id(prefix: str, items: list[dict[str, Any]], id_field: str) -> str:
    max_index = 0
    marker = f"{prefix}-"
    for item in items:
        value = str(item.get(id_field) or "")
        if not value.startswith(marker):
            continue
        try:
            max_index = max(max_index, int(value.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{max_index + 1:03d}"
