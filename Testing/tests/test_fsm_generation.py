from __future__ import annotations

from backend.agent.tools.fsm import generate_fsm_tests


def test_borrow_success_flow_generates_available_to_borrowed_case():
    result = generate_fsm_tests(
        "REQ-AUT-008",
        "The system shall create a borrowing record when an existing member borrows an existing book with availableCopies greater than 0.",
    )

    case = _case_covering(result, "FSM-TRANS-001")

    assert "FSM-STATE-001" in case["covered_states"]
    assert "FSM-STATE-002" in case["covered_states"]
    assert "availableCopies > 0" in case["expected_result"]
    assert _has_step(case, "Then state becomes borrowed")


def test_borrow_failure_flows_cover_book_missing_stock_and_member_missing():
    result = generate_fsm_tests(
        "REQ-AUT-BORROW-FAIL",
        "Borrowing fails when the book does not exist, availableCopies is 0, or member does not exist.",
    )

    no_stock = _case_covering(result, "FSM-TRANS-004")
    missing_book = _case_covering(result, "FSM-TRANS-005")
    missing_member = _case_covering(result, "FSM-TRANS-006")

    assert "availableCopies = 0" in no_stock["expected_result"]
    assert "book.id is missing or not found" in missing_book["expected_result"]
    assert "member.id is missing or not found" in missing_member["expected_result"]
    assert {"FSM-STATE-001", "FSM-STATE-004"}.issubset(set(no_stock["covered_states"]))


def test_return_success_flow_generates_borrowed_returned_and_available_cases():
    result = generate_fsm_tests(
        "REQ-AUT-012",
        "The system shall return a borrowed book when PUT /api/return/{recordId} is called for an existing unreturned record.",
    )

    returned_case = _case_covering(result, "FSM-TRANS-002")
    available_case = _case_covering(result, "FSM-TRANS-003")

    assert {"FSM-STATE-002", "FSM-STATE-003"}.issubset(set(returned_case["covered_states"]))
    assert {"FSM-STATE-003", "FSM-STATE-001"}.issubset(set(available_case["covered_states"]))
    assert "returnDate is null" in returned_case["expected_result"]


def test_return_failure_flows_cover_duplicate_and_missing_record():
    result = generate_fsm_tests(
        "REQ-AUT-013",
        "Return fails when the borrowing record has already been returned or recordId is not found.",
    )

    duplicate_return = _case_covering(result, "FSM-TRANS-007")
    missing_record = _case_covering(result, "FSM-TRANS-008")

    assert "record already has returnDate set" in duplicate_return["expected_result"]
    assert "recordId is not found" in missing_record["expected_result"]


def test_fallback_fsm_generation_is_deterministic_and_traceable():
    first = generate_fsm_tests(
        "REQ-GENERIC-001",
        "The system shall send an email after a scheduled task runs.",
    )
    second = generate_fsm_tests(
        "REQ-GENERIC-001",
        "The system shall send an email after a scheduled task runs.",
    )

    assert first == second
    assert [state["name"] for state in first["data"]["fsm_model"]["states"]] == [
        "INITIAL",
        "PROCESSING",
        "SUCCESS",
        "FAILED",
    ]
    assert first["data"]["test_cases"][0]["traceability"]["chain"]


def test_mermaid_and_traceability_are_in_generation_output():
    result = generate_fsm_tests("REQ-AUT-MERMAID", "A member borrows and returns a book.")

    assert result["data"]["mermaid"].startswith("stateDiagram-v2")
    assert "FSM-TRANS-001" in result["data"]["mermaid"]
    assert result["data"]["traceability"]["requirement_id"] == "REQ-AUT-MERMAID"
    assert result["data"]["traceability"]["test_cases"]


def test_generation_respects_max_depth_and_reports_gaps():
    result = generate_fsm_tests(
        "REQ-AUT-DEPTH",
        "A member borrows and returns a book.",
        max_depth=1,
    )

    assert result["metadata"]["uncovered_transition_count"] > 0
    assert result["data"]["traceability"]["uncovered_transitions"]


def _case_covering(result: dict, transition_id: str) -> dict:
    for case in result["data"]["test_cases"]:
        if transition_id in case["covered_transitions"]:
            return case
    raise AssertionError(f"No test case covers {transition_id}")


def _has_step(case: dict, text: str) -> bool:
    needle = text.lower()
    return any(needle in step.lower() for step in case["steps"])
