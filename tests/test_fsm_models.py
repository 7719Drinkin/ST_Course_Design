from __future__ import annotations

from backend.agent.tools.fsm import (
    FSMCoverageItem,
    FSMGenerationResult,
    FSMModel,
    FSMState,
    FSMTestCase,
    FSMTransition,
)


def test_fsm_model_dataclasses_are_serializable_and_stable():
    state = FSMState("FSM-STATE-001", "AVAILABLE", "Can be borrowed.", is_initial=True)
    transition = FSMTransition(
        transition_id="FSM-TRANS-001",
        source_state="FSM-STATE-001",
        target_state="FSM-STATE-002",
        event="BorrowBook",
        condition="availableCopies > 0",
        action="create borrowing record",
        requirement_id="REQ-AUT-008",
        coverage_item_id="COV-AUT-FSM-001",
    )
    model = FSMModel(
        model_id="FSM-MODEL-001",
        requirement_id="REQ-AUT-008",
        states=[state],
        transitions=[transition],
        initial_state="FSM-STATE-001",
    )

    assert model.to_dict() == {
        "model_id": "FSM-MODEL-001",
        "requirement_id": "REQ-AUT-008",
        "name": "Finite State Machine",
        "description": "",
        "initial_state": "FSM-STATE-001",
        "states": [state.to_dict()],
        "transitions": [transition.to_dict()],
    }


def test_fsm_coverage_and_test_case_traceability_serializes():
    coverage_item = FSMCoverageItem(
        coverage_item_id="COV-AUT-FSM-001",
        requirement_id="REQ-AUT-008",
        description="Cover borrow transition.",
        strategy="ALL_TRANSITIONS",
        target_type="transition",
        target_id="FSM-TRANS-001",
        covered_states=["FSM-STATE-001", "FSM-STATE-002"],
        covered_transitions=["FSM-TRANS-001"],
        standard_ref="FSM_TRANSITION_COVERAGE",
    )
    test_case = FSMTestCase(
        test_id="TC-AUT-FSM-001",
        requirement_id="REQ-AUT-008",
        coverage_item_ids=["COV-AUT-FSM-001"],
        title="Borrow available book",
        preconditions=["Current state is Available."],
        steps=["When trigger BorrowBook."],
        expected_results=["State becomes Borrowed."],
        covered_states=["FSM-STATE-001", "FSM-STATE-002"],
        covered_transitions=["FSM-TRANS-001"],
        traceability={
            "chain": ["REQ-AUT-008 -> COV-AUT-FSM-001 -> TC-AUT-FSM-001"],
        },
    )

    assert coverage_item.to_dict()["technique"] == "FSM"
    assert test_case.to_dict()["coverage_item_id"] == "COV-AUT-FSM-001"
    assert test_case.to_dict()["expected_result"] == "State becomes Borrowed."
    assert test_case.to_dict()["traceability"]["chain"] == [
        "REQ-AUT-008 -> COV-AUT-FSM-001 -> TC-AUT-FSM-001"
    ]


def test_fsm_generation_result_to_dict_keeps_output_contract():
    model = FSMModel(
        model_id="FSM-MODEL-001",
        requirement_id="REQ-AUT-008",
        states=[FSMState("FSM-STATE-001", "AVAILABLE", is_initial=True)],
        transitions=[],
        initial_state="FSM-STATE-001",
    )
    result = FSMGenerationResult(success=True, model=model, metadata={"case_count": 0})

    payload = result.to_dict()

    assert payload["success"] is True
    assert payload["model"]["model_id"] == "FSM-MODEL-001"
    assert payload["metadata"] == {"case_count": 0}
