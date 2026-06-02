from __future__ import annotations

from .models import FSMCoverageItem, FSMModel, FSMTestCase, FSMTransition
from .path_generator import generate_transition_paths


def generate_fsm_test_cases(
    model: FSMModel,
    coverage_items: list[FSMCoverageItem],
    max_depth: int = 6,
) -> list[FSMTestCase]:
    """Generate deterministic FSM test cases from transition paths."""

    paths = generate_transition_paths(model, max_depth=max_depth)
    state_names = {state.state_id: state.name for state in model.states}
    coverage_by_target = _coverage_items_by_target(coverage_items)
    test_cases: list[FSMTestCase] = []

    for index, path in enumerate(paths, start=1):
        if not path:
            continue
        test_id = _test_id(index)
        covered_states = _covered_states_for_path(path)
        covered_transitions = [transition.transition_id for transition in path]
        coverage_item_ids = _coverage_item_ids_for_path(path, covered_states, coverage_by_target)

        test_cases.append(
            FSMTestCase(
                test_id=test_id,
                requirement_id=model.requirement_id,
                coverage_item_ids=coverage_item_ids,
                title=_title_for_path(index, path, state_names),
                preconditions=_preconditions_for_path(model, path, state_names),
                steps=_steps_for_path(path, state_names),
                expected_results=_expected_results_for_path(path, state_names),
                covered_states=covered_states,
                covered_transitions=covered_transitions,
                traceability=_traceability_for_case(
                    model.requirement_id,
                    coverage_item_ids,
                    test_id,
                    covered_states,
                    covered_transitions,
                ),
            )
        )

    return test_cases


def _coverage_items_by_target(
    coverage_items: list[FSMCoverageItem],
) -> dict[tuple[str, str], list[FSMCoverageItem]]:
    result: dict[tuple[str, str], list[FSMCoverageItem]] = {}
    for item in coverage_items:
        result.setdefault((item.target_type, item.target_id), []).append(item)
    return result


def _covered_states_for_path(path: list[FSMTransition]) -> list[str]:
    covered: list[str] = []
    for transition in path:
        for state_id in (transition.source_state, transition.target_state):
            if state_id not in covered:
                covered.append(state_id)
    return covered


def _coverage_item_ids_for_path(
    path: list[FSMTransition],
    covered_states: list[str],
    coverage_by_target: dict[tuple[str, str], list[FSMCoverageItem]],
) -> list[str]:
    item_ids: list[str] = []
    for transition in path:
        for item in coverage_by_target.get(("transition", transition.transition_id), []):
            _append_unique(item_ids, item.coverage_item_id)
        _append_unique(item_ids, transition.coverage_item_id)
    for state_id in covered_states:
        for item in coverage_by_target.get(("state", state_id), []):
            _append_unique(item_ids, item.coverage_item_id)
    return item_ids


def _title_for_path(
    index: int,
    path: list[FSMTransition],
    state_names: dict[str, str],
) -> str:
    states = [state_names.get(path[0].source_state, path[0].source_state)]
    states.extend(state_names.get(transition.target_state, transition.target_state) for transition in path)
    return f"FSM path {index:03d}: {' -> '.join(states)}"


def _preconditions_for_path(
    model: FSMModel,
    path: list[FSMTransition],
    state_names: dict[str, str],
) -> list[str]:
    first_transition = path[0]
    return [
        (
            f"FSM model {model.model_id} starts from "
            f"{state_names.get(model.initial_state, model.initial_state)} ({model.initial_state})."
        ),
        (
            f"Current state is {state_names.get(first_transition.source_state, first_transition.source_state)} "
            f"({first_transition.source_state})."
        ),
        f"Transition guard is prepared: {first_transition.condition}.",
    ]


def _steps_for_path(
    path: list[FSMTransition],
    state_names: dict[str, str],
) -> list[str]:
    steps: list[str] = []
    for transition in path:
        source_name = state_names.get(transition.source_state, transition.source_state)
        target_name = state_names.get(transition.target_state, transition.target_state)
        steps.extend(
            [
                f"Given current state is {source_name} ({transition.source_state}).",
                f"When trigger {transition.event} with condition: {transition.condition}.",
                f"Then state becomes {target_name} ({transition.target_state}).",
                f"And execute action: {transition.action}",
            ]
        )
    return steps


def _expected_results_for_path(
    path: list[FSMTransition],
    state_names: dict[str, str],
) -> list[str]:
    results: list[str] = []
    for transition in path:
        target_name = state_names.get(transition.target_state, transition.target_state)
        results.append(
            (
                f"{transition.transition_id}: when {transition.condition}, "
                f"the target state is {target_name} ({transition.target_state}) "
                f"and the expected action is {transition.action}"
            )
        )
    return results


def _traceability_for_case(
    requirement_id: str,
    coverage_item_ids: list[str],
    test_id: str,
    covered_states: list[str],
    covered_transitions: list[str],
) -> dict[str, object]:
    return {
        "requirement_id": requirement_id,
        "coverage_item_ids": list(coverage_item_ids),
        "test_id": test_id,
        "chain": [
            f"{requirement_id} -> {coverage_item_id} -> {test_id}"
            for coverage_item_id in coverage_item_ids
        ],
        "covered_states": list(covered_states),
        "covered_transitions": list(covered_transitions),
    }


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _test_id(index: int) -> str:
    return f"TC-AUT-FSM-{index:03d}"
