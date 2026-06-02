from __future__ import annotations

"""FSM path generation tests."""

from backend.agent.tools.fsm import (
    FSMModel,
    FSMState,
    FSMTransition,
    find_uncovered_transitions,
    generate_transition_paths,
    parse_fsm_from_requirement,
)


def test_generate_transition_paths_is_stable_and_covers_transitions():
    model = parse_fsm_from_requirement(
        "REQ-AUT-008",
        "The system shall create a borrowing record when a member borrows an available book.",
    )

    first = generate_transition_paths(model, max_depth=6)
    second = generate_transition_paths(model, max_depth=6)

    assert _path_ids(first) == _path_ids(second)
    assert all(path[0].source_state == model.initial_state for path in first if path)
    assert {
        transition_id
        for path in first
        for transition_id in [transition.transition_id for transition in path]
    } == {transition.transition_id for transition in model.transitions}


def test_generate_transition_paths_respects_max_depth():
    model = parse_fsm_from_requirement(
        "REQ-AUT-008",
        "The system shall create a borrowing record when a member borrows an available book.",
    )

    paths = generate_transition_paths(model, max_depth=1)

    assert paths
    assert all(len(path) <= 1 for path in paths)
    assert find_uncovered_transitions(model, paths)


def test_unreachable_transition_is_left_as_coverage_gap():
    model = _model_with_unreachable_transition()

    paths = generate_transition_paths(model, max_depth=4)
    uncovered = find_uncovered_transitions(model, paths)

    assert all(path[0].source_state == model.initial_state for path in paths if path)
    assert [transition.transition_id for transition in uncovered] == ["FSM-TRANS-999"]


def _path_ids(paths: list[list[FSMTransition]]) -> list[list[str]]:
    return [[transition.transition_id for transition in path] for path in paths]


def _model_with_unreachable_transition() -> FSMModel:
    states = [
        FSMState("FSM-STATE-001", "INITIAL", is_initial=True),
        FSMState("FSM-STATE-002", "SUCCESS", is_terminal=True),
        FSMState("FSM-STATE-999", "ORPHAN"),
    ]
    transitions = [
        FSMTransition(
            transition_id="FSM-TRANS-001",
            source_state="FSM-STATE-001",
            target_state="FSM-STATE-002",
            event="complete",
            condition="valid request",
            action="return success",
            requirement_id="REQ-UNREACHABLE",
            coverage_item_id="COV-AUT-FSM-001",
        ),
        FSMTransition(
            transition_id="FSM-TRANS-999",
            source_state="FSM-STATE-999",
            target_state="FSM-STATE-999",
            event="orphan",
            condition="unreachable source state",
            action="remain unreachable",
            requirement_id="REQ-UNREACHABLE",
            coverage_item_id="COV-AUT-FSM-999",
        ),
    ]
    return FSMModel(
        model_id="FSM-MODEL-UNREACHABLE",
        requirement_id="REQ-UNREACHABLE",
        states=states,
        transitions=transitions,
        initial_state="FSM-STATE-001",
    )
