from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..util import evidence, make_id, next_index, now_iso, to_dicts
from ..store import TARGET_TO_COLLECTION, workflow_store
from .schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResult,
    AnalysisSummary,
    RegenerateRequest,
    RegenerateResponse,
    RevisionRecord,
    RevisionsRequest,
    RevisionsResponse,
)

try:
    from backend.agent.pipeline import AgentPipeline
    from backend.agent.prompts.prompt_builder import PromptBuilder
    from backend.agent.tools.clients.llm_client import LLMClient
except ModuleNotFoundError:
    from agent.pipeline import AgentPipeline
    from agent.prompts.prompt_builder import PromptBuilder
    from agent.tools.clients.llm_client import LLMClient


class EvidenceImproveService:
    def save_revision(self, request: RevisionsRequest) -> RevisionsResponse:
        if not request.reason.strip():
            raise HTTPException(status_code=400, detail="revision reason is required")
        existing = workflow_store.get_list(request.session_id, "revisions")
        change_kind = _revision_change_kind(request.before, request.after)
        revision = RevisionRecord(
            revision_id=make_id("REV", next_index(existing, "revision_id", "REV")),
            session_id=request.session_id,
            target_type=request.target_type,
            target_id=request.target_id,
            before=request.before,
            after=request.after,
            reason=request.reason,
            created_by=request.created_by,
            created_at=now_iso(),
            change_kind=change_kind,
            change_summary=_revision_change_summary(request.target_type, request.target_id, request.before, request.after),
        )
        affected_ids = workflow_store.apply_revision_status(
            request.session_id,
            request.target_type,
            request.target_id,
            request.before,
            request.after,
        )
        workflow_store.save_many(request.session_id, "revisions", [revision], "revision_id")
        return RevisionsResponse(revision=revision, affected_ids=affected_ids)

    async def regenerate(self, request: RegenerateRequest) -> RegenerateResponse:
        revision = workflow_store.find_revision(request.session_id, request.revision_id)
        if revision is None:
            raise HTTPException(status_code=404, detail=f"revision_id not found: {request.revision_id}")

        state = _workflow_state(request.session_id, request.current_state)
        created, updated, unchanged, deprecated = _revision_impact(revision, state)
        generated_created, generated_updated, generated_deprecated, prompt_evidence = await _regenerate_impacted_tests(
            request.session_id,
            revision,
            state,
            updated,
            deprecated,
            request.current_state,
        )
        _merge_grouped(created, generated_created)
        _merge_grouped(updated, generated_updated)
        _merge_grouped(deprecated, generated_deprecated)

        workflow_store.save_many(request.session_id, "prompt_evidence", prompt_evidence, "evidence_id")
        return RegenerateResponse(
            session_id=request.session_id,
            created=created,
            updated=updated,
            unchanged=unchanged,
            deprecated=deprecated,
            prompt_evidence=prompt_evidence,
        )

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        requirements = to_dicts(request.requirements) or workflow_store.get_list(request.session_id, "requirements")
        coverage_items = to_dicts(request.coverage_items) or workflow_store.get_list(request.session_id, "coverage_items")
        strategies = to_dicts(request.strategies) or workflow_store.get_list(request.session_id, "strategies")
        test_cases = to_dicts(request.test_cases) or workflow_store.get_list(request.session_id, "test_cases")
        revisions = to_dicts(request.revisions) or workflow_store.get_list(request.session_id, "revisions")
        _save_analysis_inputs(request, requirements, coverage_items, strategies, test_cases, revisions)

        revised_ids = _revised_ids(revisions, coverage_items, strategies, test_cases)
        strategies_by_coverage: dict[str, list[dict[str, Any]]] = {}
        for strategy in strategies:
            strategies_by_coverage.setdefault(str(strategy.get("coverage_item_id")), []).append(strategy)
        tests_by_coverage: dict[str, list[dict[str, Any]]] = {}
        for test_case in test_cases:
            tests_by_coverage.setdefault(str(test_case.get("coverage_item_id")), []).append(test_case)

        results: list[AnalysisResult] = []
        for requirement in requirements:
            requirement_id = str(requirement.get("requirement_id"))
            related_coverage = [
                item for item in coverage_items if item.get("requirement_id") == requirement_id
            ]
            if not related_coverage:
                results.append(
                    AnalysisResult(
                        requirement_id=requirement_id,
                        status="missing",
                        gap="No COV-AUT coverage item is mapped to this requirement.",
                    )
                )
                continue

            for coverage in related_coverage:
                coverage_id = str(coverage.get("coverage_item_id"))
                related_tests = tests_by_coverage.get(coverage_id, [])
                related_strategies = strategies_by_coverage.get(coverage_id, [])
                strategy_id = str((related_strategies[0] if related_strategies else {}).get("strategy_id") or "")
                if not related_tests:
                    results.append(
                        AnalysisResult(
                            requirement_id=requirement_id,
                            coverage_item_id=coverage_id,
                            strategy_id=strategy_id,
                            status="missing",
                            gap="Coverage item has no generated test case.",
                        )
                    )
                    continue

                for test_case in related_tests:
                    test_id = str(test_case.get("test_id"))
                    improved = bool({requirement_id, coverage_id, test_id} & revised_ids)
                    results.append(
                        AnalysisResult(
                            requirement_id=requirement_id,
                            coverage_item_id=coverage_id,
                            strategy_id=str(test_case.get("strategy_id") or strategy_id),
                            test_id=test_id,
                            status="improved" if improved else "covered",
                            gap="",
                            improvement="Human revision affected this mapping." if improved else "",
                        )
                    )

        known_requirement_ids = {str(item.get("requirement_id")) for item in requirements if item.get("requirement_id")}
        covered_coverage_ids = {str(item.get("coverage_item_id")) for item in coverage_items if item.get("coverage_item_id")}
        analyzed_coverage_ids = {item.coverage_item_id for item in results if item.coverage_item_id}
        for coverage in coverage_items:
            coverage_id = str(coverage.get("coverage_item_id") or "")
            requirement_id = str(coverage.get("requirement_id") or "")
            if coverage_id in analyzed_coverage_ids:
                continue
            status = "needs_review" if requirement_id not in known_requirement_ids else "missing"
            results.append(
                AnalysisResult(
                    requirement_id=requirement_id,
                    coverage_item_id=coverage_id,
                    strategy_id=str((strategies_by_coverage.get(coverage_id, [{}])[0]).get("strategy_id") or ""),
                    status=status,
                    gap="Coverage item has no mapped requirement." if status == "needs_review" else "Coverage item is not linked to a generated test case.",
                )
            )

        analyzed_test_ids = {item.test_id for item in results if item.test_id}
        for test_case in test_cases:
            test_id = str(test_case.get("test_id") or "")
            coverage_id = str(test_case.get("coverage_item_id") or "")
            if test_id in analyzed_test_ids:
                continue
            results.append(
                AnalysisResult(
                    requirement_id=str(test_case.get("requirement_id") or ""),
                    coverage_item_id=coverage_id,
                    strategy_id=str(test_case.get("strategy_id") or ""),
                    test_id=test_id,
                    status="needs_review" if coverage_id not in covered_coverage_ids else "covered",
                    gap="Test case references an unknown coverage item." if coverage_id not in covered_coverage_ids else "",
                )
            )

        summary = AnalysisSummary(
            requirements_count=len(requirements),
            coverage_items_count=len(coverage_items),
            test_cases_count=len(test_cases),
            missing_count=sum(1 for item in results if item.status == "missing"),
            improved_count=sum(1 for item in results if item.status == "improved"),
        )
        workflow_store.save_many(request.session_id, "analysis_results", results, replace_all=True)
        return AnalysisResponse(
            session_id=request.session_id,
            analysis_results=results,
            summary=summary,
        )


def _save_analysis_inputs(
    request: AnalysisRequest,
    requirements: list[dict[str, Any]],
    coverage_items: list[dict[str, Any]],
    strategies: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
    revisions: list[dict[str, Any]],
) -> None:
    if request.requirements is not None:
        workflow_store.save_many(request.session_id, "requirements", requirements, "requirement_id", replace_all=True)
    if request.coverage_items is not None:
        workflow_store.save_many(request.session_id, "coverage_items", coverage_items, "coverage_item_id", replace_all=True)
    if request.strategies is not None:
        workflow_store.save_many(request.session_id, "strategies", strategies, "strategy_id", replace_all=True)
    if request.test_cases is not None:
        workflow_store.save_many(request.session_id, "test_cases", test_cases, "test_id", replace_all=True)
    if request.revisions is not None:
        workflow_store.save_many(request.session_id, "revisions", revisions, "revision_id", replace_all=True)


def _workflow_state(session_id: str, current_state: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    state = current_state or {}
    return {
        "requirements": to_dicts(state.get("requirements")) or workflow_store.get_list(session_id, "requirements"),
        "parsed_requirements": to_dicts(state.get("parsed_requirements")) or workflow_store.get_list(session_id, "parsed_requirements"),
        "risk_results": to_dicts(state.get("risk_results")) or workflow_store.get_list(session_id, "risk_results"),
        "coverage_items": to_dicts(state.get("coverage_items")) or workflow_store.get_list(session_id, "coverage_items"),
        "strategies": to_dicts(state.get("strategies")) or workflow_store.get_list(session_id, "strategies"),
        "test_cases": to_dicts(state.get("test_cases")) or workflow_store.get_list(session_id, "test_cases"),
    }


def _revision_impact(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    target_type = str(revision.get("target_type") or "")
    target_id = str(revision.get("target_id") or "")
    after = revision.get("after") or {}
    before = revision.get("before") or {}
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
        collection, _ = target_collection
        created[collection] = [after]
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


async def _regenerate_impacted_tests(
    session_id: str,
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    updated: dict[str, Any],
    deprecated: dict[str, Any],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[Any]]:
    impacted_coverage = _impacted_coverage_items(revision, state, updated)
    impacted_tests = _impacted_test_cases(state, updated, deprecated, impacted_coverage)
    if not impacted_coverage and not impacted_tests:
        raise HTTPException(
            status_code=422,
            detail="revision does not affect coverage items or test cases, so LLM regeneration cannot be scoped",
        )

    impact, prompt_evidence = await _llm_revision_impact(
        session_id,
        revision,
        state,
        impacted_coverage,
        impacted_tests,
        current_state,
    )
    created, regenerated, deprecated_tests, pipeline_evidence = await _rerun_pipeline_from_impact(
        session_id,
        impact,
        revision,
        state,
        impacted_coverage,
        impacted_tests,
        current_state,
    )
    return created, regenerated, deprecated_tests, [*prompt_evidence, *pipeline_evidence]


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
    session_id: str,
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[Any]]:
    prompt_input = _revision_regenerate_prompt_input(
        session_id,
        revision,
        state,
        impacted_coverage,
        impacted_tests,
        current_state,
    )
    prompt = PromptBuilder().build("revision_regenerate", prompt_input)
    try:
        payload = await LLMClient().generate_json(prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM revision impact analysis failed: {exc}",
        ) from exc

    impact = _normalize_revision_impact(payload, revision, impacted_coverage, impacted_tests)
    prompt_evidence = _revision_regenerate_evidence(
        session_id,
        str(revision.get("revision_id") or ""),
        prompt,
        prompt_input,
        impact,
    )
    return impact, prompt_evidence


def _revision_regenerate_prompt_input(
    session_id: str,
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "revision": revision,
        "related_requirements": _related_requirements(state, revision, impacted_coverage, impacted_tests),
        "related_risk_results": _related_risk_results(state, impacted_coverage, impacted_tests),
        "impacted_coverage_items": impacted_coverage,
        "impacted_strategies": _related_strategies(state, impacted_coverage, impacted_tests),
        "impacted_test_cases": impacted_tests,
        "next_test_id_hint": make_id("TC-AUT", next_index(state.get("test_cases", []), "test_id", "TC-AUT")),
        "rag_context": str((current_state or {}).get("rag_context") or ""),
    }


def _normalize_revision_impact(
    payload: dict[str, Any],
    revision: dict[str, Any],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="LLM revision impact output must be a JSON object")

    reentry_stage = str(payload.get("reentry_stage") or "").strip()
    allowed = {"parse", "risk", "strategy", "generate", "fsm", "oracle", "analysis"}
    if reentry_stage not in allowed:
        raise HTTPException(status_code=502, detail=f"invalid LLM reentry_stage: {reentry_stage or '<empty>'}")

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
) -> list[Any]:
    existing_evidence = workflow_store.get_list(session_id, "prompt_evidence")
    return [
        evidence(
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
            next_index(existing_evidence, "evidence_id", "PE-AUT"),
            "LLM-based revision impact interpretation for scoped AgentPipeline rerun.",
        )
    ]


async def _rerun_pipeline_from_impact(
    session_id: str,
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[Any]]:
    stage = str(impact.get("reentry_stage") or "")
    if stage == "analysis":
        return {}, {}, {}, []
    if stage == "oracle":
        return await _rerun_from_oracle(session_id, impact, revision, state, impacted_tests, current_state)
    if stage == "fsm":
        return await _rerun_from_fsm(session_id, impact, revision, state, impacted_coverage, impacted_tests, current_state)
    if stage == "generate":
        return await _rerun_from_generate(session_id, impact, revision, state, impacted_coverage, impacted_tests, current_state)
    if stage == "strategy":
        return await _rerun_from_strategy(session_id, impact, revision, state, impacted_coverage, impacted_tests, current_state)
    if stage == "risk":
        return await _rerun_from_risk(session_id, impact, revision, state, impacted_tests, current_state)
    if stage == "parse":
        return await _rerun_from_parse(session_id, impact, revision, state, current_state)
    raise HTTPException(status_code=502, detail=f"unsupported reentry_stage: {stage}")


async def _rerun_from_generate(
    session_id: str,
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[Any]]:
    coverage_items = _selected_coverage_items(impact, state, impacted_coverage)
    ep_bva_dt = [_agent_coverage_item(item, state) for item in coverage_items if _coverage_technique(item) != "FSM"]
    fsm_items = [item for item in coverage_items if _coverage_technique(item) == "FSM"]

    created: dict[str, Any] = {}
    updated: dict[str, Any] = {}
    deprecated: dict[str, Any] = {}
    evidence_items: list[Any] = []

    if ep_bva_dt:
        result = await AgentPipeline().generate_tests(
            ep_bva_dt,
            _agent_risk_items(state, coverage_items),
            _rag_context(current_state),
        )
        generated_tests = _model_dump_list(result.test_cases)
        _mark_revision(generated_tests, revision, "pipeline_regenerated")
        c, u = _split_created_updated(generated_tests, state.get("test_cases", []), "test_id")
        _add_group(created, "test_cases", c)
        _add_group(updated, "test_cases", u)
        evidence_items.extend(
            _agent_prompt_records_to_evidence(
                session_id,
                result.prompts_used,
                str(revision.get("revision_id") or ""),
                {"stage": "generate", "test_case_count": len(generated_tests)},
                "Revision re-entered AgentPipeline.generate_tests.",
            )
        )

    if fsm_items:
        fsm_created, fsm_updated, fsm_deprecated, fsm_evidence = await _rerun_from_fsm(
            session_id,
            impact,
            revision,
            state,
            fsm_items,
            impacted_tests,
            current_state,
        )
        _merge_grouped(created, fsm_created)
        _merge_grouped(updated, fsm_updated)
        _merge_grouped(deprecated, fsm_deprecated)
        evidence_items.extend(fsm_evidence)

    _deprecate_replaced_tests(deprecated, impacted_tests, created, updated, revision)
    _save_regenerate_outputs(session_id, created, updated, deprecated)
    return created, updated, deprecated, evidence_items


async def _rerun_from_fsm(
    session_id: str,
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[Any]]:
    coverage_items = impacted_coverage or _selected_coverage_items(impact, state, [])
    result = await AgentPipeline().generate_fsm(
        requirements=_related_requirements(state, revision, coverage_items, impacted_tests),
        parsed_requirements=state.get("parsed_requirements", []),
        coverage_items=coverage_items,
        rag_context=_rag_context(current_state),
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
    _save_regenerate_outputs(session_id, created, updated, deprecated)
    workflow_store.save_object(session_id, "fsm", fsm_payload)
    evidence_items = _agent_prompt_records_to_evidence(
        session_id,
        result.prompts_used,
        str(revision.get("revision_id") or ""),
        {"stage": "fsm", "test_case_count": len(generated_tests)},
        "Revision re-entered AgentPipeline.generate_fsm.",
    )
    return created, updated, deprecated, evidence_items


async def _rerun_from_oracle(
    session_id: str,
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[Any]]:
    test_cases = impacted_tests or _selected_test_cases(impact, state)
    if not test_cases:
        raise HTTPException(status_code=422, detail="oracle reentry requires at least one affected test case")
    result = await AgentPipeline().generate_oracles(
        test_cases,
        requirements=_related_requirements(state, revision, [], test_cases),
        rag_context=_rag_context(current_state),
    )
    oracle_results = _model_dump_list(result.oracle_results)
    _mark_revision(oracle_results, revision, "pipeline_regenerated")
    updated = {"oracle_results": oracle_results} if oracle_results else {}
    _save_regenerate_outputs(session_id, {}, updated, {})
    evidence_items = _agent_prompt_records_to_evidence(
        session_id,
        result.prompts_used,
        str(revision.get("revision_id") or ""),
        {"stage": "oracle", "oracle_result_count": len(oracle_results)},
        "Revision re-entered AgentPipeline.generate_oracles.",
    )
    return {}, updated, {}, evidence_items


async def _rerun_from_strategy(
    session_id: str,
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[Any]]:
    coverage_items = _selected_coverage_items(impact, state, impacted_coverage)
    if not coverage_items:
        raise HTTPException(status_code=422, detail="strategy reentry requires affected coverage items")
    pipeline = AgentPipeline()
    strategy_result = await pipeline.assign_strategy(
        _coverage_goals_from_coverage_items(coverage_items),
        _analyzed_requirements_for_items(state, coverage_items),
        _agent_risk_items(state, coverage_items),
        _rag_context(current_state),
    )
    new_coverage = _model_dump_list(strategy_result.coverage_items)
    _mark_revision(new_coverage, revision, "pipeline_regenerated")
    workflow_store.save_many(session_id, "coverage_items", new_coverage, "coverage_item_id")

    generate_created, generate_updated, generate_deprecated, generate_evidence = await _rerun_from_generate(
        session_id,
        {**impact, "affected_ids": {**impact.get("affected_ids", {}), "coverage_items": [item.get("coverage_item_id") for item in new_coverage]}},
        revision,
        {**state, "coverage_items": _merge_items(state.get("coverage_items", []), new_coverage, "coverage_item_id")},
        new_coverage,
        impacted_tests,
        current_state,
    )
    _add_group(generate_updated, "coverage_items", new_coverage)
    evidence_items = _agent_prompt_records_to_evidence(
        session_id,
        strategy_result.prompts_used,
        str(revision.get("revision_id") or ""),
        {"stage": "strategy", "coverage_item_count": len(new_coverage)},
        "Revision re-entered AgentPipeline.assign_strategy.",
    )
    return generate_created, generate_updated, generate_deprecated, [*evidence_items, *generate_evidence]


async def _rerun_from_risk(
    session_id: str,
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_tests: list[dict[str, Any]],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[Any]]:
    requirements = _analyzed_requirements_for_items(
        state,
        _selected_requirements(impact, state),
    )
    if not requirements:
        raise HTTPException(status_code=422, detail="risk reentry requires affected analyzed requirements")
    pipeline = AgentPipeline()
    risk_result = await pipeline.analyze_risk(requirements, _rag_context(current_state))
    risk_items = _model_dump_list(risk_result.risk_analysis)
    workflow_store.save_many(session_id, "risk_results", risk_items, "requirement_id")

    strategy_created, strategy_updated, strategy_deprecated, strategy_evidence = await _rerun_from_strategy(
        session_id,
        impact,
        revision,
        {**state, "risk_results": _merge_items(state.get("risk_results", []), risk_items, "requirement_id")},
        _selected_coverage_items(impact, state, []),
        impacted_tests,
        current_state,
    )
    _add_group(strategy_updated, "risk_results", risk_items)
    evidence_items = _agent_prompt_records_to_evidence(
        session_id,
        risk_result.prompts_used,
        str(revision.get("revision_id") or ""),
        {"stage": "risk", "risk_count": len(risk_items)},
        "Revision re-entered AgentPipeline.analyze_risk.",
    )
    return strategy_created, strategy_updated, strategy_deprecated, [*evidence_items, *strategy_evidence]


async def _rerun_from_parse(
    session_id: str,
    impact: dict[str, Any],
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    current_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[Any]]:
    requirement_text = _revision_requirement_text(revision, state)
    if not requirement_text:
        raise HTTPException(status_code=422, detail="parse reentry requires revised requirement text")
    pipeline = AgentPipeline()
    parse_result = await pipeline.parse_requirements(requirement_text, _rag_context(current_state))
    parsed_requirements = _model_dump_list(parse_result.requirements)
    analyzed_requirements = _model_dump_list(parse_result.analyzed_requirements)
    workflow_store.save_many(session_id, "parsed_requirements", parsed_requirements, "requirement_id")

    risk_result = await pipeline.analyze_risk(parse_result.analyzed_requirements, _rag_context(current_state))
    risk_items = _model_dump_list(risk_result.risk_analysis)
    workflow_store.save_many(session_id, "risk_results", risk_items, "requirement_id")

    coverage_result = await pipeline.identify_coverage(
        parse_result.analyzed_requirements,
        risk_result.risk_analysis,
        _rag_context(current_state),
    )
    strategy_result = await pipeline.assign_strategy(
        coverage_result.coverage_goals,
        parse_result.analyzed_requirements,
        risk_result.risk_analysis,
        _rag_context(current_state),
    )
    coverage_items = _model_dump_list(strategy_result.coverage_items)
    workflow_store.save_many(session_id, "coverage_items", coverage_items, "coverage_item_id")

    generate_result = await pipeline.generate_tests(
        strategy_result.coverage_items,
        risk_result.risk_analysis,
        _rag_context(current_state),
    )
    test_cases = _model_dump_list(generate_result.test_cases)
    _mark_revision(test_cases, revision, "pipeline_regenerated")
    workflow_store.save_many(session_id, "test_cases", test_cases, "test_id")

    updated = {
        "parsed_requirements": parsed_requirements,
        "risk_results": risk_items,
        "coverage_items": coverage_items,
        "test_cases": test_cases,
    }
    evidence_items: list[Any] = []
    for records, stage, count_key, count in [
        (parse_result.prompts_used, "parse", "parsed_requirement_count", len(parsed_requirements)),
        (risk_result.prompts_used, "risk", "risk_count", len(risk_items)),
        (coverage_result.prompts_used, "coverage", "coverage_goal_count", len(coverage_result.coverage_goals)),
        (strategy_result.prompts_used, "strategy", "coverage_item_count", len(coverage_items)),
        (generate_result.prompts_used, "generate", "test_case_count", len(test_cases)),
    ]:
        evidence_items.extend(
            _agent_prompt_records_to_evidence(
                session_id,
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
        str(item.get("requirement_id") or "")
        for item in [*impacted_coverage, *impacted_tests]
        if item.get("requirement_id")
    )
    requirement_ids = {item for item in requirement_ids if item}
    return _dedupe_by_id(
        [
            item
            for item in [*state.get("requirements", []), *state.get("parsed_requirements", [])]
            if str(item.get("requirement_id") or "") in requirement_ids
        ],
        "requirement_id",
    )


def _related_risk_results(
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage_ids = {
        str(item.get("coverage_item_id") or "")
        for item in [*impacted_coverage, *impacted_tests]
        if item.get("coverage_item_id")
    }
    requirement_ids = {
        str(item.get("requirement_id") or "")
        for item in [*impacted_coverage, *impacted_tests]
        if item.get("requirement_id")
    }
    target_ids = coverage_ids | requirement_ids
    return [
        item for item in state.get("risk_results", [])
        if str(item.get("target_id") or item.get("requirement_id") or "") in target_ids
    ]


def _related_strategies(
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage_ids = {
        str(item.get("coverage_item_id") or "")
        for item in impacted_coverage
        if item.get("coverage_item_id")
    }
    coverage_ids.update(
        coverage_id
        for item in impacted_tests
        for coverage_id in _test_case_coverage_ids(item)
    )
    strategy_ids = {
        str(item.get("strategy_id") or "")
        for item in impacted_tests
        if item.get("strategy_id")
    }
    return [
        item for item in state.get("strategies", [])
        if str(item.get("coverage_item_id") or "") in coverage_ids
        or str(item.get("strategy_id") or "") in strategy_ids
    ]


def _test_case_coverage_ids(test_case: dict[str, Any]) -> set[str]:
    raw_ids = (
        test_case.get("coverage_item_ids")
        or test_case.get("coverage_items")
        or test_case.get("covered_coverage_item_ids")
    )
    coverage_ids = {str(item) for item in raw_ids if str(item).strip()} if isinstance(raw_ids, list) else set()
    coverage_id = str(test_case.get("coverage_item_id") or "")
    if coverage_id:
        coverage_ids.add(coverage_id)
    return coverage_ids


def _dedupe_by_id(items: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        item_id = str(item.get(id_field) or "")
        key = item_id or repr(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _model_dump_list(items: list[Any]) -> list[dict[str, Any]]:
    return [
        item.model_dump(mode="json", by_alias=True) if hasattr(item, "model_dump") else dict(item)
        for item in items
    ]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _rag_context(current_state: dict[str, Any] | None) -> str:
    return str((current_state or {}).get("rag_context") or "")


def _coverage_technique(item: dict[str, Any]) -> str:
    technique = item.get("technique")
    if not technique and isinstance(item.get("techniques"), list) and item["techniques"]:
        technique = item["techniques"][0]
    return str(technique or "EP")


def _selected_coverage_items(
    impact: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = set(_string_list((impact.get("affected_ids") or {}).get("coverage_items")))
    items = [item for item in state.get("coverage_items", []) if str(item.get("coverage_item_id") or "") in ids]
    return _dedupe_by_id([*fallback, *items], "coverage_item_id")


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
        "coverage_goal_id": str(item.get("coverage_goal_id") or f"CG-{coverage_id}" or "CG-AUT-REV"),
        "requirement_id": str(item.get("requirement_id") or ""),
        "technique": technique,
        "description": str(item.get("description") or item.get("expected_action") or "Revised coverage item"),
        "conditions": list(item.get("conditions") or []),
        "data_ranges": list(item.get("data_ranges") or []),
        "input_fields": list(item.get("input_fields") or []),
        "expected_action": str(item.get("expected_action") or item.get("description") or "System behavior follows the revised coverage item."),
        "strategy_rationale": str(item.get("strategy_rationale") or strategy.get("reason") or "Designer revision requires downstream regeneration."),
        "technique_reason": str(item.get("technique_reason") or strategy.get("reason") or f"{technique} remains assigned to the revised coverage item."),
    }


def _strategy_for_coverage(state: dict[str, list[dict[str, Any]]], coverage_id: str) -> dict[str, Any]:
    for item in state.get("strategies", []):
        if str(item.get("coverage_item_id") or "") == coverage_id:
            return item
    return {}


def _agent_risk_items(
    state: dict[str, list[dict[str, Any]]],
    coverage_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirement_ids = {
        str(item.get("requirement_id") or "")
        for item in coverage_items
        if item.get("requirement_id")
    }
    coverage_to_requirement = {
        str(item.get("coverage_item_id") or ""): str(item.get("requirement_id") or "")
        for item in coverage_items
    }
    result: list[dict[str, Any]] = []
    for item in state.get("risk_results", []):
        target_id = str(item.get("target_id") or item.get("requirement_id") or "")
        requirement_id = str(item.get("requirement_id") or "")
        if not requirement_id and target_id in coverage_to_requirement:
            requirement_id = coverage_to_requirement[target_id]
        if requirement_id not in requirement_ids:
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
                "risk_reason": str(item.get("risk_reason") or item.get("reason") or "Risk context from current workflow state."),
            }
        )
    return _dedupe_by_id(result, "requirement_id")


def _bounded_int(value: Any, default: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default
    return min(5, max(1, number))


def _analyzed_requirements_for_items(
    state: dict[str, list[dict[str, Any]]],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirement_ids = {
        str(item.get("requirement_id") or "")
        for item in items
        if item.get("requirement_id")
    }
    candidates = [*state.get("parsed_requirements", []), *state.get("requirements", [])]
    selected = [
        item for item in candidates
        if not requirement_ids or str(item.get("requirement_id") or "") in requirement_ids
    ]
    analyzed: list[dict[str, Any]] = []
    for item in selected:
        description = str(item.get("description") or item.get("raw_text") or item.get("text") or item.get("title") or "")
        if not description:
            continue
        analyzed.append(
            {
                "requirement_id": str(item.get("requirement_id") or ""),
                "module": str(item.get("module") or "revision"),
                "description": description,
                "input_fields": list(item.get("input_fields") or []),
                "data_ranges": list(item.get("data_ranges") or []),
                "conditions": list(item.get("conditions") or []),
                "business_rules": list(item.get("business_rules") or []),
                "expected_action": str(item.get("expected_action") or description),
            }
        )
    return _dedupe_by_id(analyzed, "requirement_id")


def _coverage_goals_from_coverage_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "coverage_goal_id": str(item.get("coverage_goal_id") or f"CG-{item.get('coverage_item_id')}" or "CG-AUT-REV"),
            "requirement_id": str(item.get("requirement_id") or ""),
            "goal": str(item.get("description") or item.get("expected_action") or "Regenerate revised coverage goal"),
            "related_inputs": list(item.get("input_fields") or []),
            "related_conditions": list(item.get("conditions") or []),
            "expected_action": str(item.get("expected_action") or item.get("description") or "System behavior follows the revised coverage item."),
        }
        for item in items
    ]


def _merge_items(existing: list[dict[str, Any]], updates: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    merged = {str(item.get(id_field) or ""): item for item in existing if item.get(id_field)}
    for item in updates:
        item_id = str(item.get(id_field) or "")
        if item_id:
            merged[item_id] = item
    return list(merged.values())


def _mark_revision(items: list[dict[str, Any]], revision: dict[str, Any], status: str) -> None:
    for item in items:
        item["review_status"] = status
        item["regenerated_from_revision"] = revision.get("revision_id")


def _split_created_updated(
    items: list[dict[str, Any]],
    existing: list[dict[str, Any]],
    id_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    existing_ids = {str(item.get(id_field) or "") for item in existing if item.get(id_field)}
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    for item in items:
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
    updated_ids = {
        str(item.get("test_id") or "")
        for item in updated.get("test_cases", [])
        if isinstance(item, dict)
    }
    if not created.get("test_cases"):
        return
    replacements: list[dict[str, Any]] = []
    for item in impacted_tests:
        test_id = str(item.get("test_id") or "")
        if not test_id or test_id in updated_ids:
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


def _save_regenerate_outputs(
    session_id: str,
    created: dict[str, Any],
    updated: dict[str, Any],
    deprecated: dict[str, Any],
) -> None:
    for group in (created, updated, deprecated):
        for key, value in group.items():
            if key == "fsm":
                workflow_store.save_object(session_id, "fsm", value)
            elif isinstance(value, list):
                id_field = _collection_id_field(key)
                if key == "risk_results" and value and "target_id" not in value[0]:
                    id_field = "requirement_id"
                workflow_store.save_many(session_id, key, value, id_field)


def _agent_prompt_records_to_evidence(
    session_id: str,
    records: list[Any],
    target_id: str,
    output_summary: dict[str, Any],
    note: str,
) -> list[Any]:
    start_index = next_index(
        workflow_store.get_list(session_id, "prompt_evidence"),
        "evidence_id",
        "PE-AUT",
    )
    result: list[Any] = []
    for offset, record in enumerate(records):
        item = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
        result.append(
            evidence(
                session_id,
                str(item.get("name") or item.get("prompt_name") or "agent_pipeline"),
                target_id,
                {"prompt": item.get("prompt", "")},
                output_summary,
                start_index + offset,
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
        existing_ids = {
            str(item.get(_collection_id_field(key) or "id") or "")
            for item in target[key]
            if isinstance(item, dict)
        }
        for item in values:
            item_id = str(item.get(_collection_id_field(key) or "id") or "") if isinstance(item, dict) else ""
            if item_id and item_id in existing_ids:
                target[key] = [
                    item if str(existing.get(_collection_id_field(key) or "id") or "") == item_id else existing
                    for existing in target[key]
                ]
            else:
                target[key].append(item)


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
        "coverage_items": "coverage_item_id",
        "strategies": "strategy_id",
        "test_cases": "test_id",
    }.get(collection)


def _is_deprecated(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or item.get("review_status") or "").lower()
    return status in {"rejected", "deprecated"}


def _revision_change_kind(before: dict[str, Any], after: dict[str, Any]) -> str:
    if not before and after:
        return "create"
    if before and _is_deprecated(after):
        return "deprecate"
    if before and after:
        return "update"
    return "unknown"


def _revision_change_summary(
    target_type: str,
    target_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> str:
    fields = sorted(set(before) | set(after))
    if not fields:
        return f"{target_type} {target_id} revision has no field-level delta."
    changed = [
        field
        for field in fields
        if str(before.get(field, "")) != str(after.get(field, ""))
    ]
    return f"{target_type} {target_id} changed fields: {', '.join(changed or fields)}"


def _revised_ids(
    revisions: list[dict[str, Any]],
    coverage_items: list[dict[str, Any]],
    strategies: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
) -> set[str]:
    state = {
        "requirements": [],
        "parsed_requirements": [],
        "risk_results": [],
        "coverage_items": coverage_items,
        "strategies": strategies,
        "test_cases": test_cases,
    }
    ids: set[str] = set()
    for revision in revisions:
        ids.add(str(revision.get("target_id") or ""))
        for values in _affected_ids(
            str(revision.get("target_type") or ""),
            str(revision.get("target_id") or ""),
            state,
        ).values():
            ids.update(values)
    return {item for item in ids if item}
