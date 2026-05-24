from __future__ import annotations

from itertools import islice, product

from .models import (
    CoverageItem,
    DecisionRule,
    GeneratedTestCase,
    ParsedRequirement,
    build_algorithm_output,
    make_coverage_goal_id,
    make_indexed_coverage_item_id,
    make_spec_id,
    make_test_id,
    standard_ref_for,
)
from .parser import parse_requirement


def generate_dt_cases(
    requirement_id: str,
    requirement_text: str,
    context: dict | None = None,
) -> dict:
    context = context or {}
    requirement = parse_requirement(requirement_id, requirement_text, context)
    conditions = _condition_columns(requirement)
    rules = decision_rules(
        conditions,
        requirement.expected_action,
        max_rules=_max_decision_rules(context),
    )
    coverage_items: list[CoverageItem] = []
    test_cases: list[GeneratedTestCase] = []

    for index, rule in enumerate(rules, start=1):
        coverage_item = _coverage_item(requirement, rule, index)
        coverage_items.append(coverage_item)
        test_cases.append(_test_case(requirement, coverage_item, rule, index))

    return build_algorithm_output(coverage_items, test_cases, ["DT"])


def decision_rules(
    conditions: list[str],
    expected_action: str,
    max_rules: int = 8,
) -> list[DecisionRule]:
    normalized_conditions = [condition for condition in conditions if condition]
    if not normalized_conditions:
        normalized_conditions = ["Requirement preconditions are satisfied"]

    combinations = product([False, True], repeat=len(normalized_conditions))
    rules: list[DecisionRule] = []
    for index, values in enumerate(islice(combinations, max_rules), start=1):
        rules.append(
            DecisionRule(
                rule_id=f"RULE-{index:03d}",
                conditions=dict(zip(normalized_conditions, values, strict=True)),
                expected_action=expected_action,
            )
        )
    return rules


def _condition_columns(requirement: ParsedRequirement) -> list[str]:
    columns: list[str] = []
    for condition in requirement.business_rules + requirement.conditions:
        value = condition.strip()
        if value and value not in columns:
            columns.append(value)
    return columns or ["Requirement preconditions are satisfied"]


def _coverage_item(requirement: ParsedRequirement, rule: DecisionRule, index: int) -> CoverageItem:
    return CoverageItem(
        coverage_item_id=make_indexed_coverage_item_id(requirement.requirement_id, "DT", index),
        coverage_goal_id=make_coverage_goal_id(requirement.requirement_id, "DT"),
        requirement_id=requirement.requirement_id,
        technique="DT",
        description=f"DT rule {rule.rule_id}",
        conditions=[f"{condition}={value}" for condition, value in rule.conditions.items()],
        data_ranges=[],
        input_fields=list(rule.conditions),
        expected_action=_expected_for_rule(requirement.expected_action, rule),
        strategy_rationale="Deterministically expand boolean condition combinations into decision-table rules.",
        standard_ref=standard_ref_for("DT"),
    )


def _test_case(
    requirement: ParsedRequirement,
    coverage_item: CoverageItem,
    rule: DecisionRule,
    index: int,
) -> GeneratedTestCase:
    return GeneratedTestCase(
        test_id=make_test_id(requirement.requirement_id, index, "DT"),
        requirement_id=requirement.requirement_id,
        coverage_item_id=coverage_item.coverage_item_id,
        spec_id=make_spec_id(requirement.requirement_id, "DT", index),
        technique="DT",
        title=f"DT - {rule.rule_id}",
        preconditions=[],
        input_data={
            "rule_id": rule.rule_id,
            "decision_conditions": dict(rule.conditions),
        },
        test_steps=[
            "Set each decision-table condition to the rule's boolean value.",
            "Execute the requirement behavior under test.",
            "Verify the selected decision-table action.",
        ],
        expected_result=_expected_for_rule(requirement.expected_action, rule),
        risk_level=requirement.risk_level,
        standard_ref=standard_ref_for("DT"),
    )


def _expected_for_rule(expected_action: str, rule: DecisionRule) -> str:
    false_conditions = [condition for condition, enabled in rule.conditions.items() if not enabled]
    if not false_conditions:
        return expected_action
    return "Reject or take the alternate path because: " + "; ".join(false_conditions)


def _max_decision_rules(context: dict) -> int:
    value = context.get("max_decision_rules", 8)
    try:
        return max(2, min(8, int(value)))
    except (TypeError, ValueError):
        return 8
