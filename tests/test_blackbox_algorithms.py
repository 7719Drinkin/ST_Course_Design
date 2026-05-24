from __future__ import annotations

from itertools import product

from backend.agent.tools.blackbox_algorithms import generate_deterministic_blackbox_tests


def test_deterministic_entry_generates_ep_cases_without_prompts():
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-EP-001",
        requirement_text="The system shall create a member when email is submitted.",
        techniques=["EP"],
        context={"input_fields": ["email"], "expected_action": "Return 201 Created."},
    )

    assert result["success"] is True
    assert result["metadata"]["source"] == "deterministic_blackbox_algorithms"
    assert result["prompts_used"] == []

    cases = result["data"]["test_cases"]
    assert {case["technique"] for case in cases} == {"EP"}
    assert {case["input_data"]["partition"] for case in cases} == {"valid", "invalid"}
    assert all(case["coverage_item_id"] for case in cases)
    assert all(case["risk_level"] == 3 for case in cases)
    assert all(case["standard_ref"] for case in cases)


def test_bva_generates_min_and_max_neighbor_points():
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-BVA-001",
        requirement_text="The system shall accept quantity between 1 and 10.",
        techniques=["BVA"],
        context={
            "input_fields": ["quantity"],
            "data_ranges": [{"field": "quantity", "min": 1, "max": 10, "type": "integer"}],
            "expected_action": "Accept the request.",
        },
    )

    cases = result["data"]["test_cases"]
    values = [case["input_data"]["quantity"] for case in cases]
    labels = [case["input_data"]["boundary_label"] for case in cases]

    assert values == [0, 1, 2, 9, 10, 11]
    assert labels == ["min-1", "min", "min+1", "max-1", "max", "max+1"]
    assert {case["technique"] for case in cases} == {"BVA"}


def test_bva_skips_cleanly_when_no_boundary_can_be_parsed():
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-BVA-002",
        requirement_text="The system shall list all books.",
        techniques=["BVA"],
    )

    assert result["success"] is True
    assert result["data"]["test_cases"] == []
    assert "BVA skipped" in result["metadata"]["warnings"][0]


def test_dt_generates_boolean_combination_matrix():
    conditions = ["Book exists", "Member exists", "availableCopies > 0"]
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-DT-001",
        requirement_text="The system shall create a borrowing record.",
        techniques=["DT"],
        context={
            "conditions": conditions,
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
    assert all(case["technique"] == "DT" for case in cases)


def test_context_coverage_item_id_and_risk_score_are_preserved():
    result = generate_deterministic_blackbox_tests(
        requirement_id="REQ-CTX-001",
        requirement_text="The system shall reject unavailable books.",
        techniques=["EP"],
        context={
            "input_fields": ["availableCopies"],
            "data_ranges": ["availableCopies: integer min 0 max 5"],
            "risk_scores": {"REQ-CTX-001": 5},
            "coverage_items": [
                {
                    "coverage_item_id": "COV-B-REQ-CTX-001-EP",
                    "coverage_goal_id": "GOAL-B-REQ-CTX-001",
                    "requirement_id": "REQ-CTX-001",
                    "technique": "EP",
                    "description": "Use B output coverage item.",
                }
            ],
        },
    )

    cases = result["data"]["test_cases"]
    assert cases
    assert {case["coverage_item_id"] for case in cases} == {"COV-B-REQ-CTX-001-EP"}
    assert {case["risk_level"] for case in cases} == {5}
