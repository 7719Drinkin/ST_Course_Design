"""Test case generation and optimization service.

These deterministic generators satisfy the integration contract now and expose
one service boundary for later EP/BVA/DT/FSM algorithm modules.
"""

from __future__ import annotations

from typing import Any

from backend.data_loader import filter_requirements
from backend.services.risk import priority_to_risk
from backend.services.traceability import coverage_id_for_requirement


STANDARD_REFS = {
    "EP": "ISO/IEC/IEEE 29119-4 equivalence partitioning",
    "BVA": "ISO/IEC/IEEE 29119-4 boundary value analysis",
    "DT": "ISO/IEC/IEEE 29119-4 decision table testing",
    "FSM": "ISO/IEC/IEEE 29119-4 state transition testing",
}


def build_test_cases(requirement_ids: list[str] | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for req in filter_requirements(requirement_ids):
        _, _, risk_level = priority_to_risk(req.get("priority", "Medium"))
        for idx, technique in enumerate(req.get("techniques", ["EP"])[:3], start=1):
            cases.append(
                {
                    "test_id": f"TC-{req['id'].replace('REQ-', '')}-{idx:03d}",
                    "requirement_id": req["id"],
                    "technique": technique,
                    "title": f"{req['title']} ({technique})",
                    "preconditions": req.get("conditions", []),
                    "input_data": {field: f"sample_{field}" for field in req.get("input_fields", [])[:3]},
                    "test_steps": [f"Execute {req['id']} scenario using {technique}"],
                    "expected_result": req.get("expected_action", ""),
                    "risk_level": risk_level,
                    "standard_ref": STANDARD_REFS.get(technique, "ISO/IEC/IEEE 29119-4"),
                    "status": "Draft",
                    "coverage_item_id": coverage_id_for_requirement(req),
                }
            )
    return cases


def build_oracle_results(test_ids: list[str] | None = None) -> list[dict[str, Any]]:
    ids = test_ids or [case["test_id"] for case in build_test_cases()]
    results = []
    for test_id in ids:
        needs_review = test_id.endswith("002")
        results.append(
            {
                "test_id": test_id,
                "llm_verdict": "Pass",
                "rule_verdict": "Fail" if needs_review else "Pass",
                "confidence": 0.56 if needs_review else 0.95,
                "needs_review": needs_review,
            }
        )
    return results


def optimize_suite(mode: str, test_ids: list[str] | None = None) -> dict[str, Any]:
    all_cases = build_test_cases()
    ids = test_ids or [case["test_id"] for case in all_cases]
    before = len(ids)
    after = max(1, before // 2) if mode == "risk_priority" else max(1, before - 1)
    removed_test_ids = ids[after:]
    return {
        "before_count": before,
        "after_count": after,
        "mode": mode,
        "reduction_rate": round((1 - after / before) * 100) if before else 0,
        "removed_test_ids": removed_test_ids,
    }
