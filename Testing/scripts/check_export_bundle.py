from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_export_bundle(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload.get("export_bundle", payload)


def analyze_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    requirements = _list(bundle, "requirements")
    risk_results = _list(bundle, "risk_results")
    coverage_items = _list(bundle, "coverage_items")
    test_design_specs = _list(bundle, "test_design_specs")
    test_cases = _list(bundle, "test_cases")
    oracle_results = _list(bundle, "oracle_results")
    analysis_results = _list(bundle, "analysis_results")
    fsm_summary = bundle.get("fsm_coverage_summary") or {}

    requirement_ids = _ids(requirements, "requirement_id")
    risk_ids = {
        str(item.get("requirement_id") or item.get("target_id") or "")
        for item in risk_results
        if item.get("requirement_id") or item.get("target_id")
    }
    coverage_ids = _ids(coverage_items, "coverage_item_id")
    spec_ids = _ids(test_design_specs, "spec_id")
    test_ids = [str(item.get("test_id") or "") for item in test_cases if item.get("test_id")]
    oracle_ids = _ids(oracle_results, "test_id")

    test_coverage_refs = [
        coverage_id
        for test_case in test_cases
        for coverage_id in _coverage_ids(test_case)
    ]
    covered_coverage_ids = set(test_coverage_refs)
    duplicate_test_ids = sorted(
        test_id for test_id, count in Counter(test_ids).items() if count > 1
    )
    unknown_coverage_ref_occurrences = [
        coverage_id for coverage_id in test_coverage_refs if coverage_id not in coverage_ids
    ]
    unknown_coverage_refs = sorted(set(unknown_coverage_ref_occurrences))
    unknown_spec_refs = sorted(
        {
            str(item.get("spec_id") or "")
            for item in test_cases
            if item.get("spec_id") and str(item.get("spec_id")) not in spec_ids
        }
    )
    uncovered_coverage_ids = sorted(coverage_ids - covered_coverage_ids)
    missing_oracle_ids = sorted(set(test_ids) - oracle_ids)

    return {
        "counts": {
            "requirements": len(requirements),
            "risk_results": len(risk_results),
            "coverage_items": len(coverage_items),
            "test_design_specs": len(test_design_specs),
            "test_cases": len(test_cases),
            "oracle_results": len(oracle_results),
            "analysis_results": len(analysis_results),
        },
        "risk_missing_requirement_ids": sorted(requirement_ids - risk_ids),
        "risk_missing_count": len(requirement_ids - risk_ids),
        "duplicate_test_ids": duplicate_test_ids,
        "duplicate_test_id_count": len(duplicate_test_ids),
        "unknown_coverage_refs": unknown_coverage_refs,
        "unknown_coverage_ref_count": len(unknown_coverage_refs),
        "unknown_coverage_ref_occurrence_count": len(unknown_coverage_ref_occurrences),
        "unknown_spec_refs": unknown_spec_refs,
        "unknown_spec_ref_count": len(unknown_spec_refs),
        "uncovered_coverage_ids": uncovered_coverage_ids,
        "uncovered_coverage_count": len(uncovered_coverage_ids),
        "missing_oracle_test_ids": missing_oracle_ids,
        "missing_oracle_count": len(missing_oracle_ids),
        "fsm_state_coverage_rate": fsm_summary.get("state_coverage_rate"),
        "fsm_transition_coverage_rate": fsm_summary.get("transition_coverage_rate"),
        "analysis_status_counts": dict(Counter(str(item.get("status") or "") for item in analysis_results)),
        "unsupported_behavior_hits": _unsupported_behavior_hits(bundle),
    }


def _unsupported_behavior_hits(bundle: dict[str, Any]) -> dict[str, int]:
    text = json.dumps(bundle, ensure_ascii=False).lower()
    return {
        "authorization_or_authentication": sum(text.count(token) for token in ("401", "unauthorized", "authentication", "authorization")),
        "email_format_validation": sum(text.count(token) for token in ("email format", "invalid email", "malformed email")),
        "negative_value_validation": sum(text.count(token) for token in ("negative", "less than zero", "< 0")),
    }


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


def _ids(items: list[dict[str, Any]], field: str) -> set[str]:
    return {str(item.get(field) or "") for item in items if item.get(field)}


def _list(bundle: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = bundle.get(key) or []
    return value if isinstance(value, list) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Check AutoTestDesign export bundle consistency.")
    parser.add_argument("json_path", help="Path to an exported AutoTestDesign JSON file.")
    args = parser.parse_args()

    summary = analyze_bundle(load_export_bundle(args.json_path))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
