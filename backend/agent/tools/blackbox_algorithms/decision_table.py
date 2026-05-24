from __future__ import annotations

from itertools import product

from .models import CoverageItem, DecisionRule, GeneratedTestCase, ParsedRequirement, make_spec_id, make_test_id


def generate_decision_table_cases(
    requirement: ParsedRequirement,
    coverage_item: CoverageItem,
    start_index: int = 1,
    max_conditions: int = 6,
) -> list[GeneratedTestCase]:
    conditions = requirement.conditions[:max_conditions] or ["Requirement preconditions are satisfied"]
    cases: list[GeneratedTestCase] = []
    sequence = start_index

    for rule in decision_rules(conditions, requirement.expected_action):
        false_conditions = [name for name, enabled in rule.conditions.items() if not enabled]
        cases.append(
            GeneratedTestCase(
                test_id=make_test_id(requirement.requirement_id, sequence),
                requirement_id=requirement.requirement_id,
                coverage_item_id=coverage_item.coverage_item_id,
                spec_id=make_spec_id(requirement.requirement_id, "DT"),
                technique="DT",
                title=f"DT {rule.rule_id}",
                preconditions=[],
                input_data={
                    "rule_id": rule.rule_id,
                    "decision_conditions": dict(rule.conditions),
                },
                test_steps=[
                    "Set each decision-table condition to the rule's boolean value.",
                    "Execute the requirement behavior under test.",
                    "Verify the action selected by the rule.",
                ],
                expected_result=(
                    requirement.expected_action
                    if not false_conditions
                    else "Reject or take the alternate path because: " + "; ".join(false_conditions)
                ),
                risk_level=requirement.risk_level,
                standard_ref=requirement.standard_ref,
            )
        )
        sequence += 1
    return cases


def decision_rules(conditions: list[str], expected_action: str) -> list[DecisionRule]:
    normalized_conditions = [condition for condition in conditions if condition]
    if not normalized_conditions:
        normalized_conditions = ["Requirement preconditions are satisfied"]

    rules: list[DecisionRule] = []
    for index, values in enumerate(product([False, True], repeat=len(normalized_conditions)), start=1):
        rules.append(
            DecisionRule(
                rule_id=f"RULE-{index:03d}",
                conditions=dict(zip(normalized_conditions, values, strict=True)),
                expected_action=expected_action,
            )
        )
    return rules
