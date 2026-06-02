from __future__ import annotations

from typing import Any

from .coverage import (
    ALL_STATES,
    ALL_TRANSITIONS,
    build_traceability_map,
    find_uncovered_states,
    find_uncovered_transitions,
    generate_fsm_coverage_items,
)
from .models import FSMCoverageItem, FSMModel, FSMTestCase
from .mermaid import render_mermaid
from .parser import parse_fsm_from_requirement
from .path_generator import generate_transition_paths
from .test_case_generator import generate_fsm_test_cases


def generate_fsm_tests(
    requirement_id: str,
    requirement_text: str,
    context: dict | None = None,
    strategies: list[str] | None = None,
    max_depth: int = 6,
) -> dict[str, Any]:
    """Generate FSM model, coverage items, design specs, test cases, and traceability."""

    model = parse_fsm_from_requirement(requirement_id, requirement_text, context)
    coverage_items = generate_fsm_coverage_items(model, strategies=strategies)
    paths = generate_transition_paths(model, max_depth=max_depth)
    test_cases = generate_fsm_test_cases(model, coverage_items, max_depth=max_depth)
    traceability = build_traceability_map(model, coverage_items, paths)
    traceability["test_cases"] = {
        test_case.test_id: test_case.traceability for test_case in test_cases
    }
    uncovered_states = find_uncovered_states(model, paths)
    uncovered_transitions = find_uncovered_transitions(model, paths)
    test_design_specs = _build_test_design_specs(model, coverage_items, test_cases)
    fsm_model = model.to_dict()
    mermaid = render_mermaid(model)
    fsm_model["mermaid"] = mermaid

    metadata = {
        "deterministic": True,
        "techniques": ["FSM"],
        "strategies": _strategies_from_items(coverage_items),
        "state_count": len(model.states),
        "transition_count": len(model.transitions),
        "coverage_item_count": len(coverage_items),
        "case_count": len(test_cases),
        "max_depth": max_depth,
        "uncovered_state_count": len(uncovered_states),
        "uncovered_transition_count": len(uncovered_transitions),
    }

    return {
        "success": True,
        "data": {
            "fsm_model": fsm_model,
            "mermaid": mermaid,
            "coverage_items": [item.to_dict() for item in coverage_items],
            "test_design_specs": test_design_specs,
            "test_cases": [test_case.to_dict() for test_case in test_cases],
            "traceability": traceability,
        },
        "metadata": metadata,
        "errors": [],
    }


def _build_test_design_specs(
    model: FSMModel,
    coverage_items: list[FSMCoverageItem],
    test_cases: list[FSMTestCase],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    strategy_order = [ALL_TRANSITIONS, ALL_STATES]
    item_ids_by_strategy = {
        strategy: [
            item.coverage_item_id
            for item in coverage_items
            if item.strategy == strategy
        ]
        for strategy in strategy_order
    }
    case_ids_by_item = _case_ids_by_coverage_item(test_cases)

    for index, strategy in enumerate(strategy_order, start=1):
        item_ids = item_ids_by_strategy.get(strategy, [])
        if not item_ids:
            continue
        specs.append(
            {
                "spec_id": f"SPEC-AUT-FSM-{index:03d}",
                "requirement_id": model.requirement_id,
                "technique": "FSM",
                "strategy": strategy,
                "coverage_item_ids": item_ids,
                "design_points": [
                    {
                        "coverage_item_id": coverage_item_id,
                        "related_test_ids": case_ids_by_item.get(coverage_item_id, []),
                    }
                    for coverage_item_id in item_ids
                ],
                "standard_ref": _standard_ref_for_strategy(strategy),
                "rationale": _rationale_for_strategy(strategy),
            }
        )
    return specs


def _case_ids_by_coverage_item(test_cases: list[FSMTestCase]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for test_case in test_cases:
        for coverage_item_id in test_case.coverage_item_ids:
            result.setdefault(coverage_item_id, []).append(test_case.test_id)
    return result


def _strategies_from_items(coverage_items: list[FSMCoverageItem]) -> list[str]:
    strategies: list[str] = []
    for strategy in (ALL_TRANSITIONS, ALL_STATES):
        if any(item.strategy == strategy for item in coverage_items):
            strategies.append(strategy)
    return strategies


def _standard_ref_for_strategy(strategy: str) -> str:
    if strategy == ALL_STATES:
        return "FSM_STATE_COVERAGE"
    return "FSM_TRANSITION_COVERAGE"


def _rationale_for_strategy(strategy: str) -> str:
    if strategy == ALL_STATES:
        return "Use FSM all-states coverage so every modeled lifecycle state is exercised at least once."
    return "Use FSM all-transitions coverage so each valid, failed, and exceptional state transition is exercised."
