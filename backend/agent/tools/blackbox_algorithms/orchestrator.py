from __future__ import annotations

from typing import Any

from .bva import generate_bva_cases
from .decision_table import generate_decision_table_cases
from .ep import generate_ep_cases
from .models import (
    CoverageItem,
    DEFAULT_STANDARD_REF,
    GeneratedTestCase,
    make_coverage_goal_id,
    make_coverage_item_id,
    make_spec_id,
    normalize_techniques,
)
from .parser import parse_requirement


def generate_deterministic_blackbox_tests(
    requirement_id: str,
    requirement_text: str,
    techniques: list[str] | None = None,
    context: dict | None = None,
) -> dict:
    context = context or {}
    requirement = parse_requirement(requirement_id, requirement_text, context)
    selected_techniques = normalize_techniques(
        techniques or context.get("techniques") or context.get("recommended_techniques")
    )

    coverage_items: list[CoverageItem] = []
    test_cases: list[GeneratedTestCase] = []
    warnings: list[str] = []
    next_sequence = 1

    for technique in selected_techniques:
        coverage_item = _coverage_item(requirement, technique, context)
        coverage_items.append(coverage_item)

        if technique == "EP":
            generated = generate_ep_cases(requirement, coverage_item, next_sequence)
        elif technique == "BVA":
            generated = generate_bva_cases(requirement, coverage_item, next_sequence)
            if not generated:
                warnings.append("BVA skipped because no numeric min/max or boundary could be parsed.")
        elif technique == "DT":
            max_conditions = _max_decision_conditions(context)
            generated = generate_decision_table_cases(requirement, coverage_item, next_sequence, max_conditions)
        else:
            generated = []

        test_cases.extend(generated)
        next_sequence += len(generated)

    test_case_dicts = [item.to_dict() for item in test_cases]
    return {
        "success": True,
        "data": {
            "requirements": [requirement.to_requirement_dict()],
            "analyzed_requirements": [requirement.to_analyzed_requirement_dict()],
            "coverage_goals": [_coverage_goal(item) for item in coverage_items],
            "coverage_items": [item.to_dict() for item in coverage_items],
            "test_design_specs": _test_design_specs(coverage_items, test_case_dicts),
            "test_cases": test_case_dicts,
        },
        "metadata": {
            "source": "deterministic_blackbox_algorithms",
            "techniques": selected_techniques,
            "case_count": len(test_case_dicts),
            "warnings": warnings,
        },
        "prompts_used": [],
    }


def _coverage_item(requirement, technique: str, context: dict[str, Any]) -> CoverageItem:
    matching = _matching_context_coverage_item(requirement.requirement_id, technique, context)
    coverage_item_id = str(
        matching.get("coverage_item_id")
        or matching.get("id")
        or make_coverage_item_id(requirement.requirement_id, technique)
    )
    coverage_goal_id = str(
        matching.get("coverage_goal_id")
        or make_coverage_goal_id(requirement.requirement_id, technique)
    )
    return CoverageItem(
        coverage_item_id=coverage_item_id,
        coverage_goal_id=coverage_goal_id,
        requirement_id=requirement.requirement_id,
        technique=technique,
        description=str(
            matching.get("description")
            or f"Deterministic {technique} coverage for {requirement.requirement_id}"
        ),
        conditions=list(matching.get("conditions") or requirement.conditions),
        data_ranges=requirement.data_ranges,
        input_fields=list(matching.get("input_fields") or requirement.input_fields),
        expected_action=str(matching.get("expected_action") or requirement.expected_action),
        strategy_rationale=str(
            matching.get("strategy_rationale")
            or _strategy_rationale(technique)
        ),
    )


def _matching_context_coverage_item(requirement_id: str, technique: str, context: dict[str, Any]) -> dict[str, Any]:
    coverage_items = context.get("coverage_items")
    if not isinstance(coverage_items, list):
        return {}
    for item in coverage_items:
        if not isinstance(item, dict):
            continue
        if str(item.get("requirement_id")) != requirement_id:
            continue
        if str(item.get("technique", "")).upper() == technique:
            return item
    return {}


def _coverage_goal(item: CoverageItem) -> dict[str, Any]:
    return {
        "coverage_goal_id": item.coverage_goal_id,
        "requirement_id": item.requirement_id,
        "goal": f"Cover {item.requirement_id} with deterministic {item.technique}.",
        "related_inputs": list(item.input_fields),
        "related_conditions": list(item.conditions),
        "expected_action": item.expected_action,
    }


def _test_design_specs(coverage_items: list[CoverageItem], test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for item in coverage_items:
        related_cases = [
            case
            for case in test_cases
            if case["coverage_item_id"] == item.coverage_item_id
        ]
        if not related_cases:
            continue
        specs.append(
            {
                "spec_id": make_spec_id(item.requirement_id, item.technique),
                "coverage_item_id": item.coverage_item_id,
                "requirement_id": item.requirement_id,
                "technique": item.technique,
                "design_points": [
                    {
                        "test_id": case["test_id"],
                        "title": case["title"],
                        "input_data": case["input_data"],
                        "expected_result": case["expected_result"],
                    }
                    for case in related_cases
                ],
                "standard_ref": related_cases[0].get("standard_ref") or DEFAULT_STANDARD_REF,
            }
        )
    return specs


def _strategy_rationale(technique: str) -> str:
    if technique == "EP":
        return "Create representative valid and invalid equivalence partitions."
    if technique == "BVA":
        return "Exercise values immediately below, at, and above parsed boundaries."
    return "Expand boolean condition combinations into a decision table."


def _max_decision_conditions(context: dict[str, Any]) -> int:
    value = context.get("max_decision_conditions", 6)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 6
