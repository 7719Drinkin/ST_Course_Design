from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from ..store import workflow_store
from ..util import make_id, merge_by_id, next_index, now_iso, to_dicts
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

from agent import RevisionRunnerError, regenerate_from_revision


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
            change_summary=_revision_change_summary(
                request.target_type,
                request.target_id,
                request.before,
                request.after,
            ),
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

    async def regenerate(self, request: RegenerateRequest) -> dict:
        revision = workflow_store.find_revision(request.session_id, request.revision_id)
        if revision is None:
            revision = _find_revision_in_current_state(request.session_id, request.revision_id, request.current_state)
        if revision is None:
            raise HTTPException(status_code=404, detail=f"revision_id not found: {request.revision_id}")

        state = _workflow_state(request.session_id, request.current_state)
        asyncio.create_task(_background_regenerate(
            request.session_id, revision, state,
            str((request.current_state or {}).get("rag_context") or "") or None,
        ))
        return {"session_id": request.session_id, "status": "started"}

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        requirements = to_dicts(request.requirements) or workflow_store.get_list(request.session_id, "requirements")
        coverage_items = to_dicts(request.coverage_items) or workflow_store.get_list(request.session_id, "coverage_items")
        strategies = to_dicts(request.strategies) or workflow_store.get_list(request.session_id, "strategies")
        test_cases = to_dicts(request.test_cases) or workflow_store.get_list(request.session_id, "test_cases")
        if request.test_cases is None:
            fsm_cases = workflow_store.get_list(request.session_id, "fsm_test_cases")
            test_cases = merge_by_id(test_cases, fsm_cases, "test_id")
        revisions = to_dicts(request.revisions) or workflow_store.get_list(request.session_id, "revisions")
        _save_analysis_inputs(request, requirements, coverage_items, strategies, test_cases, revisions)

        revised_ids = _meaningful_revised_ids(revisions, coverage_items, strategies, test_cases)
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
        "coverage_goals": to_dicts(state.get("coverage_goals")) or workflow_store.get_list(session_id, "coverage_goals"),
        "coverage_items": to_dicts(state.get("coverage_items")) or workflow_store.get_list(session_id, "coverage_items"),
        "strategies": to_dicts(state.get("strategies")) or workflow_store.get_list(session_id, "strategies"),
        "test_design_specs": to_dicts(state.get("test_design_specs")) or workflow_store.get_list(session_id, "test_design_specs"),
        "test_cases": to_dicts(state.get("test_cases")) or workflow_store.get_list(session_id, "test_cases"),
        "oracle_results": to_dicts(state.get("oracle_results")) or workflow_store.get_list(session_id, "oracle_results"),
        "prompt_evidence": to_dicts(state.get("prompt_evidence")) or workflow_store.get_list(session_id, "prompt_evidence"),
    }


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
        "prompt_evidence": "evidence_id",
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
        "coverage_goals": [],
        "coverage_items": coverage_items,
        "strategies": strategies,
        "test_design_specs": [],
        "test_cases": test_cases,
        "oracle_results": [],
        "prompt_evidence": [],
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


def _meaningful_revised_ids(
    revisions: list[dict[str, Any]],
    coverage_items: list[dict[str, Any]],
    strategies: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
) -> set[str]:
    return _revised_ids(
        [revision for revision in revisions if _is_meaningful_revision(revision)],
        coverage_items,
        strategies,
        test_cases,
    )


def _is_meaningful_revision(revision: dict[str, Any]) -> bool:
    before = revision.get("before") if isinstance(revision.get("before"), dict) else {}
    after = revision.get("after") if isinstance(revision.get("after"), dict) else {}
    target_type = str(revision.get("target_type") or "")
    if not before and after:
        return True

    changed_fields = {
        field
        for field in set(before) | set(after)
        if str(before.get(field, "")) != str(after.get(field, ""))
    }
    if not changed_fields:
        return False

    review_only_fields = {"status", "review_status"}
    if target_type == "test_case" and changed_fields <= review_only_fields:
        return False
    if target_type in {"coverage_item", "strategy"} and changed_fields <= {"status", "review_status", "designer_confirmed"}:
        return False
    return True


def _find_revision_in_current_state(
    session_id: str,
    revision_id: str,
    current_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    state = current_state or {}
    for item in to_dicts(state.get("revisions")):
        item_id = str(item.get("revision_id") or item.get("id") or "")
        if item_id != revision_id:
            continue
        return _normalize_current_state_revision(session_id, item)
    return None


def _normalize_current_state_revision(session_id: str, item: dict[str, Any]) -> dict[str, Any]:
    if item.get("revision_id") and item.get("target_type") and item.get("target_id"):
        return {
            **item,
            "session_id": item.get("session_id") or session_id,
            "target_type": _revision_target_type(str(item.get("target_type") or "")),
        }

    field = str(item.get("field") or "")
    return {
        "revision_id": str(item.get("revision_id") or item.get("id") or ""),
        "session_id": session_id,
        "target_type": _revision_target_type(str(item.get("entity_type") or "")),
        "target_id": str(item.get("target_id") or item.get("entity_id") or ""),
        "before": item.get("before") if isinstance(item.get("before"), dict) else {field: item.get("old_value", "")},
        "after": item.get("after") if isinstance(item.get("after"), dict) else {field: item.get("new_value", "")},
        "reason": str(item.get("reason") or "designer revision"),
        "created_by": str(item.get("created_by") or "designer"),
        "created_at": str(item.get("created_at") or item.get("timestamp") or now_iso()),
    }


def _revision_target_type(entity_type: str) -> str:
    return {
        "requirement": "requirement",
        "parsed_requirement": "parsed_requirement",
        "risk": "risk_result",
        "risk_result": "risk_result",
        "coverage": "coverage_item",
        "coverage_item": "coverage_item",
        "strategy": "strategy",
        "test_case": "test_case",
    }.get(entity_type, entity_type)


async def _background_regenerate(
    session_id: str,
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    rag_context: str | None,
) -> None:
    try:
        result = await regenerate_from_revision(revision, state, rag_context=rag_context)
        created = result.get("created", {})
        updated = result.get("updated", {})
        deprecated = result.get("deprecated", {})
        prompt_evidence = result.get("prompt_evidence", [])
        _save_regenerate_outputs(session_id, created, updated, deprecated)
        workflow_store.save_many(session_id, "prompt_evidence", prompt_evidence, "evidence_id")
    except Exception:
        pass
