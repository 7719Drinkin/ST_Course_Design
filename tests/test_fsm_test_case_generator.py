from __future__ import annotations

from backend.agent.tools.fsm import generate_fsm_tests


def test_borrow_requirement_generates_available_to_borrowed_case():
    result = generate_fsm_tests(
        "REQ-AUT-008",
        "The system shall create a borrowing record when a member borrows an available book.",
    )

    cases = result["data"]["test_cases"]
    borrow_case = _case_covering(cases, "FSM-TRANS-001")

    assert borrow_case["test_id"] == "TC-AUT-FSM-001"
    assert borrow_case["technique"] == "FSM"
    assert "FSM-STATE-001" in borrow_case["covered_states"]
    assert "FSM-STATE-002" in borrow_case["covered_states"]
    assert any("Available" in step or "AVAILABLE" in step for step in borrow_case["steps"])
    assert any("Borrowed" in step or "BORROWED" in step for step in borrow_case["steps"])
    assert borrow_case["traceability"]["chain"][0].startswith("REQ-AUT-008 -> COV-AUT-FSM-001 -> TC-AUT-FSM-001")


def test_return_requirement_generates_borrowed_returned_and_available_paths():
    result = generate_fsm_tests(
        "REQ-AUT-012",
        "The system shall return a borrowed book when PUT /api/return/{recordId} is called.",
    )

    cases = result["data"]["test_cases"]
    returned_case = _case_covering(cases, "FSM-TRANS-002")
    available_case = _case_covering(cases, "FSM-TRANS-003")

    assert {"FSM-STATE-002", "FSM-STATE-003"}.issubset(set(returned_case["covered_states"]))
    assert {"FSM-STATE-003", "FSM-STATE-001"}.issubset(set(available_case["covered_states"]))
    assert any("Returned" in step or "RETURNED" in step for step in returned_case["steps"])
    assert any("Available" in step or "AVAILABLE" in step for step in available_case["steps"])


def test_every_transition_has_test_case_coverage_and_failure_paths():
    result = generate_fsm_tests(
        "REQ-AUT-013",
        "Reject duplicate return when record already has returnDate set.",
    )

    transitions = {
        transition["transition_id"]
        for transition in result["data"]["fsm_model"]["transitions"]
    }
    covered = {
        transition_id
        for case in result["data"]["test_cases"]
        for transition_id in case["covered_transitions"]
    }

    assert transitions == covered
    assert _case_covering(result["data"]["test_cases"], "FSM-TRANS-004")
    assert _case_covering(result["data"]["test_cases"], "FSM-TRANS-005")
    assert _case_covering(result["data"]["test_cases"], "FSM-TRANS-006")
    assert _case_covering(result["data"]["test_cases"], "FSM-TRANS-007")
    assert _case_covering(result["data"]["test_cases"], "FSM-TRANS-008")


def test_fsm_output_ids_are_stable_and_generation_is_deterministic():
    first = generate_fsm_tests(
        "REQ-AUT-STABLE",
        "A member borrows a book when availableCopies > 0 and may later return it.",
    )
    second = generate_fsm_tests(
        "REQ-AUT-STABLE",
        "A member borrows a book when availableCopies > 0 and may later return it.",
    )

    assert first == second
    assert [case["test_id"] for case in first["data"]["test_cases"]] == [
        f"TC-AUT-FSM-{index:03d}"
        for index in range(1, len(first["data"]["test_cases"]) + 1)
    ]
    assert first["data"]["test_design_specs"]
    assert {spec["strategy"] for spec in first["data"]["test_design_specs"]} == {
        "ALL_STATES",
        "ALL_TRANSITIONS",
    }


def _case_covering(cases: list[dict], transition_id: str) -> dict:
    for case in cases:
        if transition_id in case["covered_transitions"]:
            return case
    raise AssertionError(f"No FSM test case covers {transition_id}")
