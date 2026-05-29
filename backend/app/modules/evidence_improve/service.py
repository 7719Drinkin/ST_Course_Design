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
    from backend.agent.prompts.prompt_builder import PromptBuilder
    from backend.agent.tools.clients.llm_client import LLMClient
except ModuleNotFoundError:
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
            detail=f"LLM revision regeneration failed: {exc}",
        ) from exc

    created, regenerated, deprecated_tests = _normalize_llm_regenerate_payload(
        payload,
        revision,
        state.get("test_cases", []),
    )
    if created.get("test_cases"):
        workflow_store.save_many(session_id, "test_cases", created["test_cases"], "test_id")
    if regenerated.get("test_cases"):
        workflow_store.save_many(session_id, "test_cases", regenerated["test_cases"], "test_id")
    if deprecated_tests.get("test_cases"):
        workflow_store.save_many(session_id, "test_cases", deprecated_tests["test_cases"], "test_id")

    prompt_evidence = _revision_regenerate_evidence(
        session_id,
        str(revision.get("revision_id") or ""),
        prompt,
        prompt_input,
        payload,
    )
    return created, regenerated, deprecated_tests, prompt_evidence


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


def _normalize_llm_regenerate_payload(
    payload: dict[str, Any],
    revision: dict[str, Any],
    existing_tests: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    created_tests = _normalize_llm_test_cases(
        _test_cases_from_payload(payload, "created"),
        revision,
        existing_tests,
        "llm_regenerated_created",
    )
    updated_tests = _normalize_llm_test_cases(
        _test_cases_from_payload(payload, "updated"),
        revision,
        existing_tests + created_tests,
        "llm_regenerated_updated",
    )
    deprecated_tests = _normalize_llm_test_cases(
        _test_cases_from_payload(payload, "deprecated"),
        revision,
        existing_tests + created_tests + updated_tests,
        "deprecated_by_revision",
        rejected=True,
    )
    return (
        {"test_cases": created_tests} if created_tests else {},
        {"test_cases": updated_tests} if updated_tests else {},
        {"test_cases": deprecated_tests} if deprecated_tests else {},
    )


def _test_cases_from_payload(payload: dict[str, Any], group: str) -> list[dict[str, Any]]:
    raw_group = payload.get(group) if isinstance(payload.get(group), dict) else {}
    test_cases = raw_group.get("test_cases") if isinstance(raw_group, dict) else []
    if not isinstance(test_cases, list):
        raise HTTPException(status_code=502, detail=f"LLM {group}.test_cases must be an array")
    return [dict(item) for item in test_cases if isinstance(item, dict)]


def _normalize_llm_test_cases(
    test_cases: list[dict[str, Any]],
    revision: dict[str, Any],
    existing_tests: list[dict[str, Any]],
    review_status: str,
    rejected: bool = False,
) -> list[dict[str, Any]]:
    next_test_index = next_index(existing_tests, "test_id", "TC-AUT")
    normalized: list[dict[str, Any]] = []
    for item in test_cases:
        test_case = dict(item)
        if not test_case.get("test_id"):
            test_case["test_id"] = make_id("TC-AUT", next_test_index)
            next_test_index += 1
        if rejected:
            test_case["status"] = "Rejected"
        else:
            test_case.setdefault("status", "Draft")
        coverage_id = str(test_case.get("coverage_item_id") or "")
        if coverage_id and not test_case.get("coverage_item_ids"):
            test_case["coverage_item_ids"] = [coverage_id]
        test_case["review_status"] = review_status
        test_case["regenerated_from_revision"] = revision.get("revision_id")
        normalized.append(test_case)
    return normalized


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
                "created": payload.get("created", {}),
                "updated": payload.get("updated", {}),
                "deprecated": payload.get("deprecated", {}),
            },
            next_index(existing_evidence, "evidence_id", "PE-AUT"),
            "LLM-based revision impact interpretation and affected test-case regeneration.",
        )
    ]


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


def _merge_grouped(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, values in source.items():
        if not values:
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
