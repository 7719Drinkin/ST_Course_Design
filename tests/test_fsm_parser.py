from __future__ import annotations

from backend.agent.tools.fsm import FSMModel, parse_fsm_from_requirement


def test_parse_library_borrowing_requirement_returns_default_lifecycle():
    model = parse_fsm_from_requirement(
        "REQ-AUT-008",
        (
            "The system shall create a borrowing record when an existing member "
            "borrows an existing book with availableCopies greater than 0."
        ),
    )

    assert isinstance(model, FSMModel)
    assert model.initial_state == "FSM-STATE-001"
    assert [state.name for state in model.states] == ["AVAILABLE", "BORROWED", "RETURNED", "REJECTED"]
    assert [transition.transition_id for transition in model.transitions] == [
        f"FSM-TRANS-{index:03d}" for index in range(1, 9)
    ]
    assert model.transitions[0].source_state == "FSM-STATE-001"
    assert model.transitions[0].target_state == "FSM-STATE-002"
    assert model.transitions[0].coverage_item_id == "COV-AUT-FSM-001"
    assert {transition.requirement_id for transition in model.transitions} == {"REQ-AUT-008"}


def test_parse_chinese_library_keywords_is_deterministic():
    text = "用户借书成功后，图书状态从可借变为已借；还书后变为已还。"

    first = parse_fsm_from_requirement("REQ-AUT-CN", text)
    second = parse_fsm_from_requirement("REQ-AUT-CN", text)

    assert first.to_dict() == second.to_dict()
    assert [state.name for state in first.states][:3] == ["AVAILABLE", "BORROWED", "RETURNED"]
    assert first.initial_state == "FSM-STATE-001"


def test_parse_unknown_requirement_returns_fallback_fsm():
    model = parse_fsm_from_requirement(
        "REQ-GENERIC-001",
        "The system shall send a notification email after the scheduled task runs.",
    )

    assert model.initial_state == "FSM-STATE-001"
    assert [state.name for state in model.states] == ["INITIAL", "PROCESSING", "SUCCESS", "FAILED"]
    assert [transition.transition_id for transition in model.transitions] == [
        "FSM-TRANS-001",
        "FSM-TRANS-002",
        "FSM-TRANS-003",
    ]
    assert {transition.coverage_item_id for transition in model.transitions} == {
        "COV-AUT-FSM-001",
        "COV-AUT-FSM-002",
        "COV-AUT-FSM-003",
    }
