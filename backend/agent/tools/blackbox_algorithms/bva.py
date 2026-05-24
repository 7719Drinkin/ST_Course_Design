from __future__ import annotations

from .models import (
    BoundaryPoint,
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


def generate_bva_cases(
    requirement_id: str,
    requirement_text: str,
    context: dict | None = None,
) -> dict:
    requirement = parse_requirement(requirement_id, requirement_text, context)
    coverage_items: list[CoverageItem] = []
    test_cases: list[GeneratedTestCase] = []
    sequence = 1

    for data_range in requirement.data_ranges:
        for point in boundary_points(data_range):
            coverage_item = _coverage_item(requirement, data_range, point, sequence)
            coverage_items.append(coverage_item)
            test_cases.append(_test_case(requirement, coverage_item, data_range, point, sequence))
            sequence += 1

    return build_algorithm_output(coverage_items, test_cases, ["BVA"])


def boundary_points(data_range: DataRange) -> list[BoundaryPoint]:
    if not data_range.has_boundary:
        return []

    step = _step(data_range)
    points: list[BoundaryPoint] = []

    if data_range.min_value is not None and data_range.max_value is not None:
        points.extend(
            [
                _point(data_range, data_range.min_value - step, "min-1"),
                _point(data_range, data_range.min_value, "min"),
                _point(data_range, data_range.min_value + step, "min+1"),
                _point(data_range, data_range.max_value - step, "max-1"),
                _point(data_range, data_range.max_value, "max"),
                _point(data_range, data_range.max_value + step, "max+1"),
            ]
        )
    else:
        boundary = data_range.min_value if data_range.min_value is not None else data_range.max_value
        if boundary is None:
            return []
        points.extend(
            [
                _point(data_range, boundary - step, "boundary-1"),
                _point(data_range, boundary, "boundary"),
                _point(data_range, boundary + step, "boundary+1"),
            ]
        )

    return _dedupe(points)


def _coverage_item(
    requirement: ParsedRequirement,
    data_range: DataRange,
    point: BoundaryPoint,
    index: int,
) -> CoverageItem:
    return CoverageItem(
        coverage_item_id=make_indexed_coverage_item_id(requirement.requirement_id, "BVA", index),
        coverage_goal_id=make_coverage_goal_id(requirement.requirement_id, "BVA"),
        requirement_id=requirement.requirement_id,
        technique="BVA",
        description=f"BVA point {point.label} for {data_range.field}",
        conditions=list(requirement.conditions),
        data_ranges=[data_range],
        input_fields=[data_range.field],
        expected_action=requirement.expected_action if point.expected_valid else "Reject the invalid boundary value.",
        strategy_rationale="Generate deterministic values immediately below, at, and above parsed boundaries.",
        standard_ref=standard_ref_for("BVA"),
    )


def _test_case(
    requirement: ParsedRequirement,
    coverage_item: CoverageItem,
    data_range: DataRange,
    point: BoundaryPoint,
    index: int,
) -> GeneratedTestCase:
    return GeneratedTestCase(
        test_id=make_test_id(requirement.requirement_id, index, "BVA"),
        requirement_id=requirement.requirement_id,
        coverage_item_id=coverage_item.coverage_item_id,
        spec_id=make_spec_id(requirement.requirement_id, "BVA", index),
        technique="BVA",
        title=f"BVA - {data_range.field} {point.label}",
        preconditions=list(requirement.conditions),
        input_data={
            data_range.field: point.value,
            "boundary_field": data_range.field,
            "boundary_label": point.label,
            "expected_valid": point.expected_valid,
        },
        test_steps=[
            f"Set {data_range.field} to the boundary value {point.value}.",
            "Execute the requirement behavior under test.",
            "Verify the boundary result.",
        ],
        expected_result=(
            requirement.expected_action
            if point.expected_valid
            else "Reject the boundary value or follow documented invalid-input handling."
        ),
        risk_level=requirement.risk_level,
        standard_ref=standard_ref_for("BVA"),
    )


def _point(data_range: DataRange, value: int | float, label: str) -> BoundaryPoint:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return BoundaryPoint(
        field=data_range.field,
        value=value,
        label=label,
        expected_valid=_is_valid(data_range, value),
    )


def _is_valid(data_range: DataRange, value: int | float) -> bool:
    if data_range.min_value is not None:
        if data_range.min_inclusive and value < data_range.min_value:
            return False
        if not data_range.min_inclusive and value <= data_range.min_value:
            return False
    if data_range.max_value is not None:
        if data_range.max_inclusive and value > data_range.max_value:
            return False
        if not data_range.max_inclusive and value >= data_range.max_value:
            return False
    return True


def _step(data_range: DataRange) -> int | float:
    return 1 if data_range.is_integer else 0.01


def _dedupe(points: list[BoundaryPoint]) -> list[BoundaryPoint]:
    result: list[BoundaryPoint] = []
    seen: set[tuple[str, int | float]] = set()
    for point in points:
        key = (point.field, point.value)
        if key not in seen:
            seen.add(key)
            result.append(point)
    return result
