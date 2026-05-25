from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agent.tools.blackbox_algorithms import (
    generate_bva_cases,
    generate_deterministic_blackbox_tests,
    generate_dt_cases,
    generate_ep_cases,
)
from agent.tools.output_validator import (
    validate_coverage_items,
    validate_test_cases,
    validate_test_design_specs,
)


def test_ep_generates_valid_and_invalid_classes_for_fields_enums_and_conditions():
    result = generate_ep_cases(
        requirement_id="REQ-EP-001",
        requirement_text="The system shall create an account when enabled is true.",
        context={
            "input_fields": ["age", "role", "enabled"],
            "data_ranges": [{"field": "age", "min": 18, "max": 60, "type": "integer"}],
            "enum_values": {"role": ["admin", "member"]},
            "expected_action": "Return 201 Created.",
        },
    )

    assert result["success"] is True
    assert result["metadata"] == {
        "deterministic": True,
        "techniques": ["EP"],
        "case_count": len(result["data"]["test_cases"]),
    }
    assert result["errors"] == []

    coverage_items = result["data"]["coverage_items"]
    cases = result["data"]["test_cases"]
    assert len(coverage_items) == len(cases)
    assert {case["technique"] for case in cases} == {"EP"}
    assert {case["standard_ref"] for case in cases} == {
        "ISO/IEC/IEEE 29119-4 equivalence partitioning"
    }
    assert {case["input_data"]["equivalence_class"] for case in cases} == {"valid", "invalid"}
    assert any(case["input_data"].get("role") == "__invalid_enum_value__" for case in cases)

    validate_coverage_items(coverage_items)
    validate_test_design_specs(result["data"]["test_design_specs"])
    validate_test_cases(cases)


def test_ep_supports_boolean_conditions_when_no_input_field_is_available():
    result = generate_ep_cases(
        requirement_id="REQ-EP-BOOL",
        requirement_text="The system shall approve access only if the user is active and not locked.",
    )

    cases = result["data"]["test_cases"]
    assert cases
    assert {case["input_data"]["equivalence_class"] for case in cases} == {"valid", "invalid"}
    assert any(case["input_data"].get("condition") for case in cases)


def test_bva_recognizes_text_ranges_and_generates_required_boundary_points():
    result = generate_bva_cases(
        requirement_id="REQ-BVA-001",
        requirement_text="The system shall accept age between 18 and 60.",
    )

    cases = result["data"]["test_cases"]
    values = [case["input_data"]["age"] for case in cases]
    labels = [case["input_data"]["boundary_label"] for case in cases]

    assert values == [17, 18, 19, 59, 60, 61]
    assert labels == ["min-1", "min", "min+1", "max-1", "max", "max+1"]
    assert {case["technique"] for case in cases} == {"BVA"}
    assert {case["standard_ref"] for case in cases} == {
        "ISO/IEC/IEEE 29119-4 boundary value analysis"
    }
    validate_coverage_items(result["data"]["coverage_items"])
    validate_test_design_specs(result["data"]["test_design_specs"])
    validate_test_cases(cases)


def test_bva_supports_single_boundary_and_password_length_patterns():
    single_boundary = generate_bva_cases(
        requirement_id="REQ-BVA-SINGLE",
        requirement_text="The system shall allow borrowing only when copies > 0.",
    )
    assert [case["input_data"]["copies"] for case in single_boundary["data"]["test_cases"]] == [-1, 0, 1]
    assert [
        case["input_data"]["boundary_label"]
        for case in single_boundary["data"]["test_cases"]
    ] == ["boundary-1", "boundary", "boundary+1"]

    password_length = generate_bva_cases(
        requirement_id="REQ-BVA-PASSWORD",
        requirement_text="The system shall accept password length 8-20.",
    )
    assert [
        case["input_data"]["password.length"]
        for case in password_length["data"]["test_cases"]
    ] == [7, 8, 9, 19, 20, 21]


def test_bva_supports_amount_greater_equal_and_less_equal_pattern():
    result = generate_bva_cases(
        requirement_id="REQ-BVA-AMOUNT",
        requirement_text="The system shall accept amount >= 0 and <= 1000.",
    )

    assert [case["input_data"]["amount"] for case in result["data"]["test_cases"]] == [
        -1,
        0,
        1,
        999,
        1000,
        1001,
    ]


def test_dt_generates_boolean_combination_matrix_from_business_rules():
    conditions = ["Book exists", "Member exists", "availableCopies > 0"]
    result = generate_dt_cases(
        requirement_id="REQ-DT-001",
        requirement_text="The system shall create a borrowing record.",
        context={
            "business_rules": conditions,
            "expected_action": "Return 201 and create a borrowing record.",
        },
    )

    cases = result["data"]["test_cases"]
    observed = {
        tuple(case["input_data"]["decision_conditions"][condition] for condition in conditions)
        for case in cases
    }

    assert len(cases) == 8
    assert observed == set(product([False, True], repeat=3))
    assert cases[-1]["expected_result"] == "Return 201 and create a borrowing record."
    assert {case["technique"] for case in cases} == {"DT"}
    assert {case["standard_ref"] for case in cases} == {
        "ISO/IEC/IEEE 29119-4 decision table testing"
    }
    validate_coverage_items(result["data"]["coverage_items"])
    validate_test_design_specs(result["data"]["test_design_specs"])
    validate_test_cases(cases)


def test_dt_caps_rule_count_at_eight_to_avoid_combination_explosion():
    result = generate_dt_cases(
        requirement_id="REQ-DT-CAP",
        requirement_text="The system shall approve when all checks pass.",
        context={"business_rules": ["A", "B", "C", "D"]},
    )

    assert len(result["data"]["test_cases"]) == 8
    assert result["metadata"]["case_count"] == 8


def test_orchestrator_filters_techniques_and_uses_unified_output_contract():
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-ONLY-BVA",
        requirement_text="The system shall accept amount >= 0 and <= 1000.",
        techniques=["BVA"],
    )

    assert set(result) == {"success", "data", "metadata", "errors"}
    assert set(result["data"]) == {"coverage_items", "test_design_specs", "test_cases"}
    assert result["success"] is True
    assert result["errors"] == []
    assert result["metadata"]["deterministic"] is True
    assert result["metadata"]["techniques"] == ["BVA"]
    assert {case["technique"] for case in result["data"]["test_cases"]} == {"BVA"}


def test_ep_deterministic_algorithm_for_borrow_requirement():
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-AUT-EP",
        requirement_text=(
            "The system shall allow a registered user to borrow a book only if "
            "the book exists and availableCopies > 0."
        ),
        techniques=["EP"],
    )

    cases = result["data"]["test_cases"]
    assert cases
    assert {case["technique"] for case in cases} == {"EP"}
    assert any(case["input_data"].get("equivalence_class") == "valid" for case in cases)
    assert any(case["input_data"].get("equivalence_class") == "invalid" for case in cases)
    assert all(case["coverage_item_id"] for case in cases)
    assert all(case["standard_ref"] for case in cases)


def test_bva_deterministic_algorithm_for_password_length_requirement():
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-AUT-BVA",
        requirement_text="The system shall accept password length between 8 and 20 characters.",
        techniques=["BVA"],
    )

    cases = result["data"]["test_cases"]
    assert cases
    assert {case["technique"] for case in cases} == {"BVA"}
    assert [
        case["input_data"]["password.length"]
        for case in cases
    ] == [7, 8, 9, 19, 20, 21]
    assert all(case["expected_result"] for case in cases)
    assert all(case["standard_ref"] for case in cases)


def test_dt_deterministic_algorithm_for_loan_approval_requirement():
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-AUT-DT",
        requirement_text=(
            "The system shall approve a loan only if the user is registered, "
            "credit score is valid, and requested amount is within limit."
        ),
        techniques=["DT"],
    )

    cases = result["data"]["test_cases"]
    expected_results = [case["expected_result"].lower() for case in cases]
    assert cases
    assert {case["technique"] for case in cases} == {"DT"}
    assert len(cases) >= 2
    assert any("approve" in expected_result or "success" in expected_result for expected_result in expected_results)
    assert any("reject" in expected_result or "failure" in expected_result for expected_result in expected_results)


def test_deterministic_output_is_stable_for_same_input():
    first = generate_deterministic_blackbox_tests(
        requirement_id="REQ-STABLE",
        requirement_text="The system shall accept password length between 8 and 20.",
        techniques=["BVA", "DT"],
        context={"business_rules": ["Password exists", "Password length is valid"]},
    )
    second = generate_deterministic_blackbox_tests(
        requirement_id="REQ-STABLE",
        requirement_text="The system shall accept password length between 8 and 20.",
        techniques=["BVA", "DT"],
        context={"business_rules": ["Password exists", "Password length is valid"]},
    )

    assert first == second
