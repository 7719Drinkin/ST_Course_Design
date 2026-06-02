from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any
import io
import zipfile

from fastapi import HTTPException

from ..util import (
    csv_bytes,
    dedupe_oracle_results,
    fsm_coverage_summary,
    fsm_coverage_items_from_test_cases,
    json_bytes,
    merge_by_id,
    strategies_from_coverage_items,
    to_dicts,
)
from ..store import workflow_store
from .schemas import (
    ExportBundle,
    ExportRequest,
    OptimizeRequest,
    OptimizeResponse,
    OptimizationResult,
)


class OptimizeExportService:
    def optimize(self, request: OptimizeRequest) -> OptimizeResponse:
        requested_test_cases = to_dicts(request.test_cases)
        stored_test_cases = _stored_all_test_cases(request.session_id)
        test_cases = (
            _merge_test_case_snapshot(stored_test_cases, requested_test_cases, include_unmentioned=False)
            if requested_test_cases
            else stored_test_cases
        )
        coverage_items = to_dicts(request.coverage_items) or workflow_store.get_list(request.session_id, "coverage_items")
        risk_results = to_dicts(request.risk_results) or workflow_store.get_list(request.session_id, "risk_results")
        if requested_test_cases:
            _sync_existing_test_case_review_fields(request.session_id, requested_test_cases)

        optimization_coverage_items = _coverage_with_fsm_items(coverage_items, test_cases)
        kept_ids = self._kept_tests(
            test_cases,
            optimization_coverage_items,
            risk_results,
            request.objective,
            request.preserve_high_risk_unique_coverage,
        )
        all_ids = [str(item.get("test_id")) for item in test_cases if item.get("test_id")]
        removed_ids = [item for item in all_ids if item not in kept_ids]
        preserved_coverage = sorted(_covered_ids([item for item in test_cases if item.get("test_id") in kept_ids]))
        warnings = []
        expected_coverage = {
            str(item.get("coverage_item_id"))
            for item in optimization_coverage_items
            if item.get("coverage_item_id")
        }
        missing = sorted(expected_coverage - set(preserved_coverage))
        if missing:
            warnings.append("Coverage items without kept tests: " + ", ".join(missing))
        rejected_only = sorted(
            coverage_id
            for coverage_id in expected_coverage
            if _tests_for_coverage(test_cases, coverage_id)
            and all(item.get("status") == "Rejected" for item in _tests_for_coverage(test_cases, coverage_id))
        )
        if rejected_only:
            warnings.append("Coverage items only covered by rejected tests; add replacement tests: " + ", ".join(rejected_only))
        tests_without_coverage = sorted(
            str(item.get("test_id"))
            for item in test_cases
            if item.get("test_id") and not _coverage_ids(item)
        )
        if tests_without_coverage:
            warnings.append("Tests without coverage mapping: " + ", ".join(tests_without_coverage))
        rejected_kept = sorted(
            str(item.get("test_id"))
            for item in test_cases
            if item.get("test_id") in kept_ids and item.get("status") == "Rejected"
        )
        if rejected_kept:
            warnings.append("Rejected tests kept because they preserve unique coverage: " + ", ".join(rejected_kept))

        result = OptimizationResult(
            objective=request.objective,
            before_count=len(test_cases),
            after_count=len(kept_ids),
            kept_test_ids=kept_ids,
            removed_test_ids=removed_ids,
            coverage_preservation=[
                f"Preserved {len(preserved_coverage)}/{len(expected_coverage or preserved_coverage)} coverage items.",
                *[f"Preserved coverage item {item}" for item in preserved_coverage],
            ],
            warnings=warnings,
        )
        workflow_store.save_object(request.session_id, "optimization_result", result)
        return OptimizeResponse(session_id=request.session_id, optimization_result=result)

    def export_bundle(self, request: ExportRequest) -> ExportBundle:
        raw = workflow_store.export_bundle(request.session_id)
        requested_test_cases = to_dicts(request.test_cases) if request.test_cases is not None else None
        requested_fsm_cases = to_dicts(request.fsm_test_cases) if request.fsm_test_cases is not None else None
        snapshot_fields = {
            "requirements": request.requirements,
            "risk_results": request.risk_results,
            "coverage_items": request.coverage_items,
            "strategies": request.strategies,
            "test_design_specs": request.test_design_specs,
            "oracle_results": request.oracle_results,
            "revisions": request.revisions,
            "prompt_evidence": request.prompt_evidence,
            "analysis_results": request.analysis_results,
        }
        for key, value in snapshot_fields.items():
            if value is not None:
                raw[key] = to_dicts(value)
        if request.fsm is not None:
            raw["fsm"] = request.fsm
        if request.optimization_result is not None:
            raw["optimization_result"] = request.optimization_result.model_dump(mode="json")
        if requested_test_cases is not None:
            fr3_snapshot = [item for item in requested_test_cases if not _is_fsm_test_case(item)]
            fsm_from_test_snapshot = [item for item in requested_test_cases if _is_fsm_test_case(item)]
            raw["test_cases"] = _merge_test_case_snapshot(raw.get("test_cases", []), fr3_snapshot)
            requested_fsm_cases = merge_by_id(
                requested_fsm_cases or [],
                fsm_from_test_snapshot,
                "test_id",
            )
        if requested_fsm_cases is not None:
            raw["fsm_test_cases"] = _merge_test_case_snapshot(raw.get("fsm_test_cases", []), requested_fsm_cases)
        raw["test_cases"] = merge_by_id(
            raw.get("test_cases", []),
            raw.get("fsm_test_cases", []),
            "test_id",
        )
        raw["coverage_items"] = merge_by_id(
            raw.get("coverage_items", []),
            fsm_coverage_items_from_test_cases(raw.get("test_cases", [])),
            "coverage_item_id",
        )
        raw["oracle_results"] = dedupe_oracle_results(raw.get("oracle_results", []))
        raw["fsm_coverage_summary"] = fsm_coverage_summary(raw.get("fsm"), raw.get("test_cases", []))
        if not raw.get("strategies"):
            raw["strategies"] = strategies_from_coverage_items(raw.get("coverage_items", []))
        if request.test_case_status == "approved_only":
            raw["test_cases"] = [
                item for item in raw.get("test_cases", []) if item.get("status") == "Approved"
            ]
            approved_ids = {str(item.get("test_id")) for item in raw.get("test_cases", [])}
            raw["oracle_results"] = [
                item for item in raw.get("oracle_results", []) if str(item.get("test_id")) in approved_ids
            ]
        if _analysis_results_stale(raw):
            raw["analysis_results"] = _build_analysis_results(raw)
        if not request.include_revisions:
            raw["revisions"] = []
        if not request.include_prompt_evidence:
            raw["prompt_evidence"] = []
        _validate_export_consistency(raw)
        return ExportBundle(**raw)

    def export_bytes(self, request: ExportRequest) -> tuple[bytes, str, str]:
        bundle = self.export_bundle(request).model_dump(mode="json", by_alias=True)
        if request.format == "json":
            return json_bytes({"export_bundle": bundle}), "application/json", "aut_design_export.json"
        if request.format == "xlsx":
            return _xlsx_bytes(bundle), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "aut_design_export.xlsx"
        return csv_bytes(bundle), "text/csv; charset=utf-8", "aut_design_export.csv"

    def _kept_tests(
        self,
        test_cases: list[dict[str, Any]],
        coverage_items: list[dict[str, Any]],
        risk_results: list[dict[str, Any]],
        objective: str,
        preserve_high_risk_unique_coverage: bool,
    ) -> list[str]:
        if not test_cases:
            return []
        risk_by_id = _risk_by_id(risk_results)
        expected_coverage = {
            str(item.get("coverage_item_id"))
            for item in coverage_items
            if item.get("coverage_item_id")
        } or _covered_ids(test_cases)
        counts = _coverage_counts(test_cases)
        kept: list[str] = []
        covered: set[str] = set()

        def priority(test_case: dict[str, Any]) -> tuple[int, int, int, str]:
            risk = _risk_for_test(test_case, risk_by_id)
            level_score = {"High": 0, "Medium": 1, "Low": 2}.get(risk.get("risk_level"), 1)
            priority_score = {"P1": 0, "P2": 1, "P3": 2}.get(
                risk.get("test_priority") or test_case.get("priority"),
                1,
            )
            status_score = {"Approved": 0, "Draft": 1, "Rejected": 2}.get(test_case.get("status"), 1)
            return level_score, priority_score, status_score, str(test_case.get("test_id"))

        eligible_tests = [item for item in test_cases if item.get("status") != "Rejected"]
        ordered = sorted(eligible_tests, key=priority) if objective == "risk_priority" else list(eligible_tests)
        if preserve_high_risk_unique_coverage:
            for item in ordered:
                coverage_ids = _coverage_ids(item)
                risk = _risk_for_test(item, risk_by_id)
                test_id = str(item.get("test_id") or "")
                if (
                    risk.get("risk_level") == "High"
                    and coverage_ids
                    and any(counts.get(coverage_id) == 1 for coverage_id in coverage_ids)
                    and test_id
                ):
                    kept.append(test_id)
                    covered.update(coverage_ids)

        remaining = [item for item in ordered if str(item.get("test_id") or "") not in kept]
        while expected_coverage - covered:
            candidate = _best_candidate(remaining, covered, risk_by_id, objective)
            if candidate is None:
                break
            test_id = str(candidate.get("test_id") or "")
            kept.append(test_id)
            covered.update(_coverage_ids(candidate))
            remaining = [item for item in remaining if str(item.get("test_id") or "") != test_id]

        for item in remaining:
            test_id = str(item.get("test_id") or "")
            if test_id and not _coverage_ids(item):
                kept.append(test_id)
        return _dedupe(kept)


def _dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


TEST_CASE_TRACEABILITY_FIELDS = {
    "test_id",
    "requirement_id",
    "coverage_item_id",
    "coverage_item_ids",
    "coverage_items",
    "covered_coverage_item_ids",
    "spec_id",
    "strategy_id",
    "technique",
}
TEST_CASE_REVIEW_FIELDS = {"status", "review_status"}


def _stored_all_test_cases(session_id: str) -> list[dict[str, Any]]:
    return merge_by_id(
        workflow_store.get_list(session_id, "test_cases"),
        workflow_store.get_list(session_id, "fsm_test_cases"),
        "test_id",
    )


def _merge_test_case_snapshot(
    official_cases: list[dict[str, Any]],
    snapshot_cases: list[dict[str, Any]],
    *,
    include_unmentioned: bool = True,
) -> list[dict[str, Any]]:
    """Apply frontend edits without allowing stale snapshots to rewrite traceability IDs."""

    snapshot_by_id = {
        str(item.get("test_id") or ""): item
        for item in snapshot_cases
        if item.get("test_id")
    }
    result: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for official in official_cases:
        test_id = str(official.get("test_id") or "")
        incoming = snapshot_by_id.get(test_id)
        if incoming:
            result.append(_merge_test_case_editable_fields(official, incoming))
            used_ids.add(test_id)
        elif include_unmentioned:
            result.append(dict(official))

    for incoming in snapshot_cases:
        test_id = str(incoming.get("test_id") or "")
        if test_id and test_id in used_ids:
            continue
        result.append(dict(incoming))
    return result


def _merge_test_case_editable_fields(
    official: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(official)
    for field, value in incoming.items():
        if field in TEST_CASE_TRACEABILITY_FIELDS:
            continue
        merged[field] = value
    return merged


def _sync_existing_test_case_review_fields(
    session_id: str,
    snapshot_cases: list[dict[str, Any]],
) -> None:
    snapshot_by_id = {
        str(item.get("test_id") or ""): item
        for item in snapshot_cases
        if item.get("test_id")
    }
    _sync_test_case_collection_review_fields(session_id, "test_cases", snapshot_by_id)
    _sync_test_case_collection_review_fields(session_id, "fsm_test_cases", snapshot_by_id)


def _sync_test_case_collection_review_fields(
    session_id: str,
    key: str,
    snapshot_by_id: dict[str, dict[str, Any]],
) -> None:
    updates: list[dict[str, Any]] = []
    for item in workflow_store.get_list(session_id, key):
        incoming = snapshot_by_id.get(str(item.get("test_id") or ""))
        if not incoming:
            continue
        updated = dict(item)
        changed = False
        for field in TEST_CASE_REVIEW_FIELDS:
            if field in incoming and incoming[field] != updated.get(field):
                updated[field] = incoming[field]
                changed = True
        if changed:
            updates.append(updated)
    if updates:
        workflow_store.save_many(session_id, key, updates, "test_id")


def _is_fsm_test_case(test_case: dict[str, Any]) -> bool:
    return str(test_case.get("technique") or "").upper() == "FSM"


def _coverage_with_fsm_items(
    coverage_items: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_ids = {
        str(item.get("coverage_item_id") or "")
        for item in coverage_items
        if item.get("coverage_item_id")
    }
    augmented = list(coverage_items)
    for test_case in test_cases:
        if str(test_case.get("technique") or "").upper() != "FSM":
            continue
        for coverage_id in _coverage_ids(test_case):
            if coverage_id in existing_ids:
                continue
            existing_ids.add(coverage_id)
            augmented.append(
                {
                    "coverage_item_id": coverage_id,
                    "requirement_id": str(test_case.get("requirement_id") or ""),
                    "technique": "FSM",
                    "description": str(test_case.get("title") or "FSM coverage inferred from test case."),
                }
            )
    return augmented


def _coverage_ids(test_case: dict[str, Any]) -> set[str]:
    raw = (
        test_case.get("coverage_item_ids")
        or test_case.get("coverage_items")
        or test_case.get("covered_coverage_item_ids")
    )
    if isinstance(raw, list):
        return {str(item) for item in raw if str(item).strip()}
    coverage_id = test_case.get("coverage_item_id")
    return {str(coverage_id)} if coverage_id else set()


def _covered_ids(test_cases: list[dict[str, Any]]) -> set[str]:
    covered: set[str] = set()
    for test_case in test_cases:
        covered.update(_coverage_ids(test_case))
    return covered


def _analysis_results_stale(bundle: dict[str, Any]) -> bool:
    analysis_results = bundle.get("analysis_results") or []
    coverage_items = bundle.get("coverage_items") or []
    test_cases = bundle.get("test_cases") or []
    coverage_ids = {
        str(item.get("coverage_item_id") or "")
        for item in coverage_items
        if item.get("coverage_item_id")
    }
    test_covered_ids = _covered_ids(test_cases)
    if not analysis_results:
        return bool(coverage_items or test_cases)
    if any(_is_bad_coverage_item_id(str(item.get("coverage_item_id") or "")) for item in coverage_items):
        return True
    for result in analysis_results:
        coverage_id = str(result.get("coverage_item_id") or "")
        status = str(result.get("status") or "")
        if coverage_id and coverage_id not in coverage_ids:
            return True
        if coverage_id in test_covered_ids and status == "missing":
            return True
    analyzed_pairs = {
        (str(item.get("coverage_item_id") or ""), str(item.get("test_id") or ""))
        for item in analysis_results
        if item.get("coverage_item_id") and item.get("test_id")
    }
    for test_case in test_cases:
        test_id = str(test_case.get("test_id") or "")
        for coverage_id in _coverage_ids(test_case):
            if coverage_id in coverage_ids and (coverage_id, test_id) not in analyzed_pairs:
                return True
    return False


def _validate_export_consistency(bundle: dict[str, Any]) -> None:
    requirements = bundle.get("requirements") or []
    risk_results = bundle.get("risk_results") or []
    coverage_items = bundle.get("coverage_items") or []
    test_design_specs = bundle.get("test_design_specs") or []
    test_cases = bundle.get("test_cases") or []
    oracle_results = bundle.get("oracle_results") or []
    fsm = bundle.get("fsm") or {}
    fsm_summary = bundle.get("fsm_coverage_summary") or {}

    errors: list[str] = []
    requirement_ids = _ids(requirements, "requirement_id")
    coverage_ids = _ids(coverage_items, "coverage_item_id")
    spec_ids = _ids(test_design_specs, "spec_id")
    test_ids = _ids(test_cases, "test_id")

    errors.extend(_duplicate_id_errors(requirements, "requirement_id", "requirements"))
    errors.extend(_duplicate_id_errors(coverage_items, "coverage_item_id", "coverage_items"))
    errors.extend(_duplicate_id_errors(test_design_specs, "spec_id", "test_design_specs"))
    errors.extend(_duplicate_id_errors(test_cases, "test_id", "test_cases"))
    errors.extend(_missing_id_errors(test_cases, "test_id", "test_cases"))

    if requirements:
        risk_ids = {
            str(item.get("requirement_id") or item.get("target_id") or "")
            for item in risk_results
            if item.get("requirement_id") or item.get("target_id")
        }
        missing_risk = sorted(requirement_ids - risk_ids)
        if missing_risk:
            errors.append("risk_results missing requirements: " + ", ".join(missing_risk))

    bad_coverage_ids = sorted(
        coverage_id for coverage_id in coverage_ids if _is_bad_coverage_item_id(coverage_id)
    )
    if bad_coverage_ids:
        errors.append("coverage_items contain invalid IDs: " + ", ".join(bad_coverage_ids))

    unknown_spec_refs = sorted(
        {
            str(item.get("coverage_item_id") or "")
            for item in test_design_specs
            if item.get("coverage_item_id") and str(item.get("coverage_item_id")) not in coverage_ids
        }
    )
    if unknown_spec_refs:
        errors.append("test_design_specs reference unknown coverage_item_id: " + ", ".join(unknown_spec_refs))

    unknown_test_refs = sorted(
        {
            coverage_id
            for test_case in test_cases
            for coverage_id in _coverage_ids(test_case)
            if coverage_id not in coverage_ids
        }
    )
    if unknown_test_refs:
        errors.append("test_cases reference unknown coverage_item_id: " + ", ".join(unknown_test_refs))

    missing_spec_refs = sorted(
        {
            str(item.get("spec_id") or "")
            for item in test_cases
            if str(item.get("technique") or "").upper() != "FSM"
            and item.get("spec_id")
            and str(item.get("spec_id")) not in spec_ids
        }
    )
    if missing_spec_refs:
        errors.append("test_cases reference unknown spec_id: " + ", ".join(missing_spec_refs))

    if coverage_items:
        covered = _covered_ids(test_cases)
        intentionally_uncovered = _intentionally_uncovered_coverage_ids(coverage_items)
        uncovered = sorted(coverage_ids - covered - intentionally_uncovered)
        if uncovered:
            errors.append("coverage_items without generated test_cases: " + ", ".join(uncovered))

    if test_cases:
        oracle_ids = _ids(oracle_results, "test_id")
        missing_oracles = sorted(test_ids - oracle_ids)
        if missing_oracles:
            errors.append("oracle_results missing test_ids: " + ", ".join(missing_oracles))

    if fsm and [item for item in test_cases if str(item.get("technique") or "").upper() == "FSM"]:
        if not fsm_summary.get("covered_states") or not fsm_summary.get("covered_transitions"):
            errors.append("fsm_coverage_summary has no covered states or transitions")

    if errors:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Export blocked because the design artifacts are not traceability-consistent. Rerun generation before exporting final evidence.",
                "errors": errors,
            },
        )


def _ids(items: list[dict[str, Any]], field: str) -> set[str]:
    return {str(item.get(field) or "") for item in items if item.get(field)}


def _duplicate_id_errors(items: list[dict[str, Any]], field: str, label: str) -> list[str]:
    counts = Counter(str(item.get(field) or "") for item in items if item.get(field))
    duplicated = sorted(item_id for item_id, count in counts.items() if count > 1)
    return [f"{label} contain duplicate {field}: " + ", ".join(duplicated)] if duplicated else []


def _missing_id_errors(items: list[dict[str, Any]], field: str, label: str) -> list[str]:
    count = sum(1 for item in items if not item.get(field))
    return [f"{label} contain {count} item(s) without {field}"] if count else []


def _intentionally_uncovered_coverage_ids(coverage_items: list[dict[str, Any]]) -> set[str]:
    allowed_statuses = {"intentionally_uncovered", "waived", "accepted_gap"}
    result: set[str] = set()
    for item in coverage_items:
        coverage_id = str(item.get("coverage_item_id") or "")
        if not coverage_id:
            continue
        status = str(
            item.get("coverage_status")
            or item.get("status")
            or item.get("review_status")
            or ""
        ).lower()
        if item.get("intentionally_uncovered") is True or status in allowed_statuses:
            result.add(coverage_id)
    return result


def _build_analysis_results(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = bundle.get("requirements") or []
    coverage_items = bundle.get("coverage_items") or []
    strategies = bundle.get("strategies") or []
    test_cases = bundle.get("test_cases") or []
    revisions = bundle.get("revisions") or []
    revised_ids = _revised_ids(revisions)

    strategies_by_coverage: dict[str, list[dict[str, Any]]] = {}
    for strategy in strategies:
        coverage_id = str(strategy.get("coverage_item_id") or "")
        if coverage_id:
            strategies_by_coverage.setdefault(coverage_id, []).append(strategy)

    tests_by_coverage: dict[str, list[dict[str, Any]]] = {}
    for test_case in test_cases:
        for coverage_id in _coverage_ids(test_case):
            tests_by_coverage.setdefault(coverage_id, []).append(test_case)

    results: list[dict[str, Any]] = []
    for requirement in requirements:
        requirement_id = str(requirement.get("requirement_id") or "")
        related_coverage = [
            item for item in coverage_items if str(item.get("requirement_id") or "") == requirement_id
        ]
        if not related_coverage:
            results.append(
                {
                    "requirement_id": requirement_id,
                    "coverage_item_id": "",
                    "strategy_id": "",
                    "test_id": "",
                    "status": "missing",
                    "gap": "No coverage item is mapped to this requirement.",
                    "improvement": "",
                }
            )
            continue

        for coverage in related_coverage:
            coverage_id = str(coverage.get("coverage_item_id") or "")
            related_tests = tests_by_coverage.get(coverage_id, [])
            strategy_id = str((strategies_by_coverage.get(coverage_id, [{}])[0]).get("strategy_id") or "")
            if not related_tests:
                results.append(
                    {
                        "requirement_id": requirement_id,
                        "coverage_item_id": coverage_id,
                        "strategy_id": strategy_id,
                        "test_id": "",
                        "status": "missing",
                        "gap": "Coverage item has no generated test case.",
                        "improvement": "",
                    }
                )
                continue
            for test_case in related_tests:
                test_id = str(test_case.get("test_id") or "")
                improved = bool({requirement_id, coverage_id, test_id} & revised_ids)
                results.append(
                    {
                        "requirement_id": requirement_id,
                        "coverage_item_id": coverage_id,
                        "strategy_id": str(test_case.get("strategy_id") or strategy_id),
                        "test_id": test_id,
                        "status": "improved" if improved else "covered",
                        "gap": "",
                        "improvement": "Human revision affected this mapping." if improved else "",
                    }
                )

    known_requirement_ids = {
        str(item.get("requirement_id") or "")
        for item in requirements
        if item.get("requirement_id")
    }
    covered_coverage_ids = {
        str(item.get("coverage_item_id") or "")
        for item in coverage_items
        if item.get("coverage_item_id")
    }
    analyzed_coverage_ids = {
        str(item.get("coverage_item_id") or "")
        for item in results
        if item.get("coverage_item_id")
    }
    for coverage in coverage_items:
        coverage_id = str(coverage.get("coverage_item_id") or "")
        requirement_id = str(coverage.get("requirement_id") or "")
        if coverage_id in analyzed_coverage_ids:
            continue
        status = "needs_review" if requirement_id not in known_requirement_ids else "missing"
        results.append(
            {
                "requirement_id": requirement_id,
                "coverage_item_id": coverage_id,
                "strategy_id": str((strategies_by_coverage.get(coverage_id, [{}])[0]).get("strategy_id") or ""),
                "test_id": "",
                "status": status,
                "gap": "Coverage item has no mapped requirement." if status == "needs_review" else "Coverage item is not linked to a generated test case.",
                "improvement": "",
            }
        )

    analyzed_test_ids = {str(item.get("test_id") or "") for item in results if item.get("test_id")}
    for test_case in test_cases:
        test_id = str(test_case.get("test_id") or "")
        if test_id in analyzed_test_ids:
            continue
        coverage_ids = _coverage_ids(test_case)
        coverage_id = next(iter(coverage_ids), str(test_case.get("coverage_item_id") or ""))
        known = bool(coverage_ids) and coverage_ids <= covered_coverage_ids
        results.append(
            {
                "requirement_id": str(test_case.get("requirement_id") or ""),
                "coverage_item_id": coverage_id,
                "strategy_id": str(test_case.get("strategy_id") or ""),
                "test_id": test_id,
                "status": "covered" if known else "needs_review",
                "gap": "" if known else "Test case references an unknown coverage item.",
                "improvement": "",
            }
        )
    return results


def _revised_ids(revisions: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for revision in revisions:
        for key in ("target_id",):
            value = revision.get(key)
            if value:
                result.add(str(value))
        for field in ("affected_ids", "related_ids"):
            values = revision.get(field)
            if isinstance(values, list):
                result.update(str(value) for value in values if str(value).strip())
    return result


def _is_bad_coverage_item_id(coverage_id: str) -> bool:
    return bool(coverage_id) and (coverage_id.startswith("COV-CG-") or "-CG-AUT-" in coverage_id)


def _tests_for_coverage(test_cases: list[dict[str, Any]], coverage_id: str) -> list[dict[str, Any]]:
    return [item for item in test_cases if coverage_id in _coverage_ids(item)]


def _coverage_counts(test_cases: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for test_case in test_cases:
        counts.update(_coverage_ids(test_case))
    return counts


def _risk_by_id(risk_results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in risk_results:
        for key in ("target_id", "requirement_id", "coverage_item_id"):
            value = item.get(key)
            if value:
                result[str(value)] = item
    return result


def _risk_for_test(test_case: dict[str, Any], risk_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for coverage_id in _coverage_ids(test_case):
        if coverage_id in risk_by_id:
            return risk_by_id[coverage_id]
    requirement_id = str(test_case.get("requirement_id") or "")
    return risk_by_id.get(requirement_id, {})


def _best_candidate(
    test_cases: list[dict[str, Any]],
    covered: set[str],
    risk_by_id: dict[str, dict[str, Any]],
    objective: str,
) -> dict[str, Any] | None:
    candidates = [item for item in test_cases if _coverage_ids(item) - covered]
    if not candidates:
        return None

    def score(test_case: dict[str, Any]) -> tuple[int, float, int, int, str]:
        uncovered_gain = len(_coverage_ids(test_case) - covered)
        risk = _risk_for_test(test_case, risk_by_id)
        risk_score = float(risk.get("risk_score") or 0)
        status_score = {"Approved": 2, "Draft": 1, "Rejected": 0}.get(test_case.get("status"), 1)
        priority_score = {"P1": 3, "P2": 2, "P3": 1}.get(
            risk.get("test_priority") or test_case.get("priority"),
            2,
        )
        if objective == "risk_priority":
            return risk_score, uncovered_gain, status_score, priority_score, str(test_case.get("test_id") or "")
        return uncovered_gain, risk_score, status_score, priority_score, str(test_case.get("test_id") or "")

    return max(candidates, key=score)


def _xlsx_bytes(bundle: dict[str, Any]) -> bytes:
    sheets = {
        "requirements": bundle.get("requirements", []),
        "risk_results": bundle.get("risk_results", []),
        "coverage_items": bundle.get("coverage_items", []),
        "strategies": bundle.get("strategies", []),
        "test_design_specs": bundle.get("test_design_specs", []),
        "test_cases": bundle.get("test_cases", []),
        "fsm_test_cases": bundle.get("fsm_test_cases", []),
        "fsm_coverage_summary": [bundle.get("fsm_coverage_summary", {})],
        "oracle_results": bundle.get("oracle_results", []),
        "revisions": bundle.get("revisions", []),
        "analysis_results": bundle.get("analysis_results", []),
        "prompt_evidence": bundle.get("prompt_evidence", []),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml(list(sheets)))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(sheets)))
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, (name, rows) in enumerate(sheets.items(), start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(name, rows))
    return output.getvalue()


def _content_types_xml(sheet_count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides}</Types>"
    )


def _root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name[:31])}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def _workbook_rels_xml(sheet_count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    rels += (
        f'<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rels}</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        "</styleSheet>"
    )


def _sheet_xml(name: str, rows: list[dict[str, Any]]) -> str:
    columns = _columns(rows)
    sheet_rows = [_row_xml(1, columns)]
    for index, item in enumerate(rows, start=2):
        sheet_rows.append(_row_xml(index, [_cell_value(item.get(column)) for column in columns]))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns or ["empty"]


def _row_xml(index: int, values: list[Any]) -> str:
    cells = "".join(
        f'<c r="{_column_name(offset)}{index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
        for offset, value in enumerate(values, start=1)
    )
    return f'<row r="{index}">{cells}</row>'


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _cell_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return str(value)
    if value is None:
        return ""
    return str(value)


def _export_id_field(key: str) -> str | None:
    return {
        "requirements": "requirement_id",
        "risk_results": "target_id",
        "coverage_items": "coverage_item_id",
        "strategies": "strategy_id",
        "test_cases": "test_id",
        "fsm_test_cases": "test_id",
        "oracle_results": "test_id",
        "revisions": "revision_id",
        "prompt_evidence": "evidence_id",
        "analysis_results": None,
    }.get(key)
