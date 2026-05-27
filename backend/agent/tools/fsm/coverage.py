from __future__ import annotations

from typing import Any

from .models import FSMCoverageItem, FSMModel, FSMState, FSMTransition
from .path_generator import generate_transition_paths


ALL_STATES = "ALL_STATES"
ALL_TRANSITIONS = "ALL_TRANSITIONS"
FSM_STATE_COVERAGE = "FSM_STATE_COVERAGE"
FSM_TRANSITION_COVERAGE = "FSM_TRANSITION_COVERAGE"
SUPPORTED_STRATEGIES = (ALL_TRANSITIONS, ALL_STATES)


def generate_fsm_coverage_items(
    model: FSMModel,
    strategies: list[str] | None = None,
) -> list[FSMCoverageItem]:
    """Generate deterministic state and transition coverage targets."""

    selected_strategies = _normalize_strategies(strategies)
    items: list[FSMCoverageItem] = []
    next_index = 1

    if ALL_TRANSITIONS in selected_strategies:
        for transition in model.transitions:
            items.append(
                FSMCoverageItem(
                    coverage_item_id=_coverage_item_id(next_index),
                    requirement_id=transition.requirement_id or model.requirement_id,
                    strategy=ALL_TRANSITIONS,
                    target_type="transition",
                    target_id=transition.transition_id,
                    description=(
                        f"Cover transition {transition.transition_id}: "
                        f"{transition.source_state} -> {transition.target_state}."
                    ),
                    covered_states=[transition.source_state, transition.target_state],
                    covered_transitions=[transition.transition_id],
                    coverage_type="transition",
                    standard_ref=FSM_TRANSITION_COVERAGE,
                )
            )
            next_index += 1

    if ALL_STATES in selected_strategies:
        for state in model.states:
            items.append(
                FSMCoverageItem(
                    coverage_item_id=_coverage_item_id(next_index),
                    requirement_id=model.requirement_id,
                    strategy=ALL_STATES,
                    target_type="state",
                    target_id=state.state_id,
                    description=f"Cover FSM state {state.name} ({state.state_id}).",
                    covered_states=[state.state_id],
                    covered_transitions=[],
                    coverage_type="state",
                    standard_ref=FSM_STATE_COVERAGE,
                )
            )
            next_index += 1

    return items


def find_uncovered_states(
    model: FSMModel,
    paths: list[list[FSMTransition]] | None = None,
) -> list[FSMState]:
    """Return model states not reached by the supplied or generated paths."""

    path_list = generate_transition_paths(model) if paths is None else paths
    covered_state_ids = _covered_state_ids(model, path_list)
    return [state for state in model.states if state.state_id not in covered_state_ids]


def find_uncovered_transitions(
    model: FSMModel,
    paths: list[list[FSMTransition]] | None = None,
) -> list[FSMTransition]:
    """Return model transitions not included in the supplied or generated paths."""

    path_list = generate_transition_paths(model) if paths is None else paths
    covered_transition_ids = _covered_transition_ids(path_list)
    return [
        transition
        for transition in model.transitions
        if transition.transition_id not in covered_transition_ids
    ]


def build_traceability_map(
    model: FSMModel,
    coverage_items: list[FSMCoverageItem] | None = None,
    paths: list[list[FSMTransition]] | None = None,
) -> dict[str, Any]:
    """Build state/transition/path traceability for coverage gap analysis."""

    item_list = coverage_items or generate_fsm_coverage_items(model)
    path_list = generate_transition_paths(model) if paths is None else paths
    state_items = _items_by_target(item_list, "state")
    transition_items = _items_by_target(item_list, "transition")
    state_paths = _state_path_indices(model, path_list)
    transition_paths = _transition_path_indices(path_list)

    return {
        "model_id": model.model_id,
        "requirement_id": model.requirement_id,
        "states": {
            state.state_id: {
                "state_id": state.state_id,
                "name": state.name,
                "coverage_item_ids": [
                    item.coverage_item_id for item in state_items.get(state.state_id, [])
                ],
                "path_indices": state_paths.get(state.state_id, []),
            }
            for state in model.states
        },
        "transitions": {
            transition.transition_id: {
                "transition_id": transition.transition_id,
                "requirement_id": transition.requirement_id,
                "coverage_item_id": transition.coverage_item_id,
                "coverage_item_ids": [
                    item.coverage_item_id
                    for item in transition_items.get(transition.transition_id, [])
                ],
                "path_indices": transition_paths.get(transition.transition_id, []),
            }
            for transition in model.transitions
        },
        "paths": [
            [transition.transition_id for transition in path]
            for path in path_list
        ],
        "uncovered_states": [
            state.state_id for state in find_uncovered_states(model, path_list)
        ],
        "uncovered_transitions": [
            transition.transition_id
            for transition in find_uncovered_transitions(model, path_list)
        ],
    }


def _normalize_strategies(strategies: list[str] | None) -> list[str]:
    requested = strategies or [ALL_TRANSITIONS, ALL_STATES]
    aliases = {
        "STATE": ALL_STATES,
        "STATES": ALL_STATES,
        "ALL_STATE": ALL_STATES,
        "TRANSITION": ALL_TRANSITIONS,
        "TRANSITIONS": ALL_TRANSITIONS,
        "ALL_TRANSITION": ALL_TRANSITIONS,
    }
    normalized: set[str] = set()
    for strategy in requested:
        value = str(strategy).strip().upper()
        value = aliases.get(value, value)
        if value not in SUPPORTED_STRATEGIES:
            raise ValueError(f"Unsupported FSM coverage strategy: {strategy}")
        normalized.add(value)
    return [strategy for strategy in SUPPORTED_STRATEGIES if strategy in normalized]


def _covered_state_ids(model: FSMModel, paths: list[list[FSMTransition]]) -> set[str]:
    covered = {model.initial_state}
    for path in paths:
        for transition in path:
            covered.add(transition.source_state)
            covered.add(transition.target_state)
    return covered


def _covered_transition_ids(paths: list[list[FSMTransition]]) -> set[str]:
    return {
        transition.transition_id
        for path in paths
        for transition in path
    }


def _items_by_target(
    items: list[FSMCoverageItem],
    target_type: str,
) -> dict[str, list[FSMCoverageItem]]:
    result: dict[str, list[FSMCoverageItem]] = {}
    for item in items:
        if item.target_type == target_type:
            result.setdefault(item.target_id, []).append(item)
    return result


def _state_path_indices(
    model: FSMModel,
    paths: list[list[FSMTransition]],
) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {model.initial_state: []}
    for path_index, path in enumerate(paths):
        if not path:
            continue
        for transition in path:
            for state_id in (transition.source_state, transition.target_state):
                indices = result.setdefault(state_id, [])
                if path_index not in indices:
                    indices.append(path_index)
    return result


def _transition_path_indices(paths: list[list[FSMTransition]]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for path_index, path in enumerate(paths):
        for transition in path:
            result.setdefault(transition.transition_id, []).append(path_index)
    return result


def _coverage_item_id(index: int) -> str:
    return f"COV-AUT-FSM-{index:03d}"
