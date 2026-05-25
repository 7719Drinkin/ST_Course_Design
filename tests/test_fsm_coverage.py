from __future__ import annotations

from backend.agent.tools.fsm import (
    ALL_STATES,
    ALL_TRANSITIONS,
    build_traceability_map,
    find_uncovered_states,
    find_uncovered_transitions,
    generate_fsm_coverage_items,
    generate_transition_paths,
    parse_fsm_from_requirement,
)


def test_generate_fsm_coverage_items_for_states_and_transitions():
    model = parse_fsm_from_requirement(
        "REQ-AUT-008",
        "A member borrows a book when availableCopies > 0 and may later return it.",
    )

    items = generate_fsm_coverage_items(model, strategies=[ALL_STATES, ALL_TRANSITIONS])
    transition_items = [item for item in items if item.target_type == "transition"]
    state_items = [item for item in items if item.target_type == "state"]

    assert len(transition_items) == len(model.transitions)
    assert len(state_items) == len(model.states)
    assert items[0].coverage_item_id == "COV-AUT-FSM-001"
    assert transition_items[0].strategy == ALL_TRANSITIONS
    assert transition_items[0].target_id == "FSM-TRANS-001"
    assert transition_items[0].standard_ref == "FSM_TRANSITION_COVERAGE"
    assert state_items[0].strategy == ALL_STATES
    assert state_items[0].target_id == "FSM-STATE-001"
    assert state_items[0].standard_ref == "FSM_STATE_COVERAGE"


def test_coverage_gap_helpers_report_full_default_model_coverage():
    model = parse_fsm_from_requirement(
        "REQ-AUT-012",
        "The system shall return a borrowed book when PUT /api/return/{recordId} is called.",
    )
    paths = generate_transition_paths(model)

    assert find_uncovered_states(model, paths) == []
    assert find_uncovered_transitions(model, paths) == []


def test_build_traceability_map_links_items_paths_and_gaps():
    model = parse_fsm_from_requirement(
        "REQ-AUT-013",
        "The system shall reject duplicate return when a borrowing record was already returned.",
    )
    items = generate_fsm_coverage_items(model)
    paths = generate_transition_paths(model, max_depth=1)

    traceability = build_traceability_map(model, items, paths)

    assert traceability["model_id"] == "FSM-MODEL-001"
    assert traceability["transitions"]["FSM-TRANS-001"]["coverage_item_ids"] == ["COV-AUT-FSM-001"]
    assert "FSM-TRANS-002" in traceability["uncovered_transitions"]
    assert traceability["states"]["FSM-STATE-001"]["coverage_item_ids"]
