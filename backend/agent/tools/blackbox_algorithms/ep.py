from __future__ import annotations

from typing import Any

from .models import CoverageItem, GeneratedTestCase, ParsedRequirement, make_spec_id, make_test_id


def generate_ep_cases(
    requirement: ParsedRequirement,
    coverage_item: CoverageItem,
    start_index: int = 1,
) -> list[GeneratedTestCase]:
    cases: list[GeneratedTestCase] = []
    sequence = start_index

    partitions = _partitions(requirement)
    for partition in partitions:
        cases.append(
            GeneratedTestCase(
                test_id=make_test_id(requirement.requirement_id, sequence),
                requirement_id=requirement.requirement_id,
                coverage_item_id=coverage_item.coverage_item_id,
                spec_id=make_spec_id(requirement.requirement_id, "EP"),
                technique="EP",
                title=f"EP {partition['name']}",
                preconditions=list(requirement.conditions),
                input_data=partition["input_data"],
                test_steps=[
                    "Prepare input data from the equivalence partition.",
                    "Execute the requirement behavior under test.",
                    "Observe the actual system response.",
                ],
                expected_result=partition["expected_result"],
                risk_level=requirement.risk_level,
                standard_ref=requirement.standard_ref,
            )
        )
        sequence += 1
    return cases


def _partitions(requirement: ParsedRequirement) -> list[dict[str, Any]]:
    partitions: list[dict[str, Any]] = []

    for data_range in requirement.data_ranges:
        valid_value = _valid_value(data_range.min_value, data_range.max_value)
        partitions.append(
            {
                "name": f"valid partition for {data_range.field}",
                "input_data": {
                    data_range.field: valid_value,
                    "partition": "valid",
                    "source_range": data_range.source,
                },
                "expected_result": requirement.expected_action,
            }
        )
        if data_range.min_value is not None:
            partitions.append(
                {
                    "name": f"invalid below-min partition for {data_range.field}",
                    "input_data": {
                        data_range.field: _minus_step(data_range.min_value),
                        "partition": "invalid",
                        "source_range": data_range.source,
                    },
                    "expected_result": "Reject the value or follow documented invalid-input handling.",
                }
            )
        if data_range.max_value is not None:
            partitions.append(
                {
                    "name": f"invalid above-max partition for {data_range.field}",
                    "input_data": {
                        data_range.field: _plus_step(data_range.max_value),
                        "partition": "invalid",
                        "source_range": data_range.source,
                    },
                    "expected_result": "Reject the value or follow documented invalid-input handling.",
                }
            )

    fields_without_ranges = [
        field
        for field in requirement.input_fields
        if field not in {item.field for item in requirement.data_ranges}
    ]
    for field in fields_without_ranges:
        partitions.append(
            {
                "name": f"valid partition for {field}",
                "input_data": {field: f"valid_{field}", "partition": "valid"},
                "expected_result": requirement.expected_action,
            }
        )
        partitions.append(
            {
                "name": f"missing-value invalid partition for {field}",
                "input_data": {field: None, "partition": "invalid"},
                "expected_result": "Reject missing or invalid input for the field.",
            }
        )

    if not partitions:
        partitions.append(
            {
                "name": "valid requirement partition",
                "input_data": {"partition": "valid"},
                "expected_result": requirement.expected_action,
            }
        )

    return partitions


def _valid_value(min_value: int | float | None, max_value: int | float | None) -> int | float | str:
    if min_value is not None and max_value is not None:
        midpoint = (float(min_value) + float(max_value)) / 2
        return int(midpoint) if midpoint.is_integer() else midpoint
    if min_value is not None:
        return _plus_step(min_value)
    if max_value is not None:
        return _minus_step(max_value)
    return "valid_value"


def _plus_step(value: int | float) -> int | float:
    return value + (1 if float(value).is_integer() else 0.01)


def _minus_step(value: int | float) -> int | float:
    return value - (1 if float(value).is_integer() else 0.01)
