from __future__ import annotations

from typing import Any

from .models import (
    CoverageItem,
    DataRange,
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


def generate_ep_cases(
    requirement_id: str,
    requirement_text: str,
    context: dict | None = None,
) -> dict:
    requirement = parse_requirement(requirement_id, requirement_text, context)
    classes = _equivalence_classes(requirement)
    coverage_items: list[CoverageItem] = []
    test_cases: list[GeneratedTestCase] = []

    for index, item in enumerate(classes, start=1):
        coverage_item = _coverage_item(requirement, item, index)
        coverage_items.append(coverage_item)
        test_cases.append(_test_case(requirement, coverage_item, item, index))

    return build_algorithm_output(coverage_items, test_cases, ["EP"])


def _equivalence_classes(requirement: ParsedRequirement) -> list[dict[str, Any]]:
    classes: list[dict[str, Any]] = []
    covered_fields: set[str] = set()

    for data_range in requirement.data_ranges:
        covered_fields.add(data_range.field)
        classes.append(
            {
                "kind": "valid",
                "field": data_range.field,
                "name": f"valid numeric range for {data_range.field}",
                "input_data": {
                    data_range.field: _valid_numeric_value(data_range),
                    "equivalence_class": "valid",
                    "source_range": data_range.source,
                },
                "expected_result": requirement.expected_action,
                "data_ranges": [data_range],
            }
        )
        classes.append(
            {
                "kind": "invalid",
                "field": data_range.field,
                "name": f"invalid numeric range for {data_range.field}",
                "input_data": {
                    data_range.field: _invalid_numeric_value(data_range),
                    "equivalence_class": "invalid",
                    "source_range": data_range.source,
                },
                "expected_result": "Reject the invalid equivalence class or follow documented invalid-input handling.",
                "data_ranges": [data_range],
            }
        )

    for field, values in sorted(requirement.enum_values.items()):
        covered_fields.add(field)
        valid_value = values[0]
        classes.append(
            {
                "kind": "valid",
                "field": field,
                "name": f"valid enum value for {field}",
                "input_data": {
                    field: valid_value,
                    "allowed_values": list(values),
                    "equivalence_class": "valid",
                },
                "expected_result": requirement.expected_action,
                "data_ranges": [],
            }
        )
        classes.append(
            {
                "kind": "invalid",
                "field": field,
                "name": f"invalid enum value for {field}",
                "input_data": {
                    field: "__invalid_enum_value__",
                    "allowed_values": list(values),
                    "equivalence_class": "invalid",
                },
                "expected_result": "Reject values outside the allowed enumeration.",
                "data_ranges": [],
            }
        )

    for field in requirement.input_fields:
        if field in covered_fields:
            continue
        covered_fields.add(field)
        classes.extend(_field_classes(field, requirement.expected_action))

    if not classes:
        for index, condition in enumerate(requirement.conditions, start=1):
            field = f"condition_{index}"
            classes.append(
                {
                    "kind": "valid",
                    "field": field,
                    "name": f"true boolean condition: {condition}",
                    "input_data": {
                        field: True,
                        "condition": condition,
                        "equivalence_class": "valid",
                    },
                    "expected_result": requirement.expected_action,
                    "data_ranges": [],
                }
            )
            classes.append(
                {
                    "kind": "invalid",
                    "field": field,
                    "name": f"false boolean condition: {condition}",
                    "input_data": {
                        field: False,
                        "condition": condition,
                        "equivalence_class": "invalid",
                    },
                    "expected_result": "Reject or take the alternate path when the boolean condition is false.",
                    "data_ranges": [],
                }
            )

    if not classes:
        classes.extend(_field_classes("request", requirement.expected_action))
    return classes


def _field_classes(field: str, expected_action: str) -> list[dict[str, Any]]:
    return [
        {
            "kind": "valid",
            "field": field,
            "name": f"valid value for {field}",
            "input_data": {field: f"valid_{field}", "equivalence_class": "valid"},
            "expected_result": expected_action,
            "data_ranges": [],
        },
        {
            "kind": "invalid",
            "field": field,
            "name": f"missing or invalid value for {field}",
            "input_data": {field: None, "equivalence_class": "invalid"},
            "expected_result": "Reject missing or invalid input for the field.",
            "data_ranges": [],
        },
    ]


def _coverage_item(requirement: ParsedRequirement, equivalence_class: dict[str, Any], index: int) -> CoverageItem:
    return CoverageItem(
        coverage_item_id=make_indexed_coverage_item_id(requirement.requirement_id, "EP", index),
        coverage_goal_id=make_coverage_goal_id(requirement.requirement_id, "EP"),
        requirement_id=requirement.requirement_id,
        technique="EP",
        description=f"EP {equivalence_class['kind']} class: {equivalence_class['name']}",
        conditions=list(requirement.conditions),
        data_ranges=list(equivalence_class["data_ranges"]),
        input_fields=[str(equivalence_class["field"])],
        expected_action=str(equivalence_class["expected_result"]),
        strategy_rationale="Deterministically create one valid and one invalid equivalence class per parsed input.",
        standard_ref=standard_ref_for("EP"),
    )


def _test_case(
    requirement: ParsedRequirement,
    coverage_item: CoverageItem,
    equivalence_class: dict[str, Any],
    index: int,
) -> GeneratedTestCase:
    return GeneratedTestCase(
        test_id=make_test_id(requirement.requirement_id, index, "EP"),
        requirement_id=requirement.requirement_id,
        coverage_item_id=coverage_item.coverage_item_id,
        spec_id=make_spec_id(requirement.requirement_id, "EP", index),
        technique="EP",
        title=f"EP - {equivalence_class['name']}",
        preconditions=list(requirement.conditions),
        input_data=dict(equivalence_class["input_data"]),
        test_steps=[
            "Select the representative value for the equivalence class.",
            "Execute the requirement behavior under test.",
            "Verify the observed result against the class expectation.",
        ],
        expected_result=str(equivalence_class["expected_result"]),
        risk_level=requirement.risk_level,
        standard_ref=standard_ref_for("EP"),
    )


def _valid_numeric_value(data_range: DataRange) -> int | float:
    if data_range.min_value is not None and data_range.max_value is not None:
        value = (float(data_range.min_value) + float(data_range.max_value)) / 2
    elif data_range.min_value is not None:
        value = float(data_range.min_value) + 1
        if not data_range.min_inclusive:
            value = float(data_range.min_value) + 1
    elif data_range.max_value is not None:
        value = float(data_range.max_value) - 1
    else:
        value = 1
    return int(value) if float(value).is_integer() else value


def _invalid_numeric_value(data_range: DataRange) -> int | float:
    if data_range.min_value is not None:
        value = float(data_range.min_value) - 1
    elif data_range.max_value is not None:
        value = float(data_range.max_value) + 1
    else:
        value = -1
    return int(value) if float(value).is_integer() else value
