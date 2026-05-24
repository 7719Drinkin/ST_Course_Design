from __future__ import annotations

from .models import BoundaryPoint, CoverageItem, DataRange, GeneratedTestCase, ParsedRequirement, make_spec_id, make_test_id


def generate_bva_cases(
    requirement: ParsedRequirement,
    coverage_item: CoverageItem,
    start_index: int = 1,
) -> list[GeneratedTestCase]:
    cases: list[GeneratedTestCase] = []
    sequence = start_index

    for data_range in requirement.data_ranges:
        for point in boundary_points(data_range):
            cases.append(
                GeneratedTestCase(
                    test_id=make_test_id(requirement.requirement_id, sequence),
                    requirement_id=requirement.requirement_id,
                    coverage_item_id=coverage_item.coverage_item_id,
                    spec_id=make_spec_id(requirement.requirement_id, "BVA"),
                    technique="BVA",
                    title=f"BVA {data_range.field} at {point.label}",
                    preconditions=list(requirement.conditions),
                    input_data={
                        data_range.field: point.value,
                        "boundary_label": point.label,
                        "boundary_field": data_range.field,
                    },
                    test_steps=[
                        f"Set {data_range.field} to {point.value}.",
                        "Execute the requirement behavior under test.",
                        "Compare the response with the expected boundary behavior.",
                    ],
                    expected_result=(
                        requirement.expected_action
                        if point.expected_valid
                        else "Reject the boundary value or follow documented invalid-input handling."
                    ),
                    risk_level=requirement.risk_level,
                    standard_ref=requirement.standard_ref,
                )
            )
            sequence += 1
    return cases


def boundary_points(data_range: DataRange) -> list[BoundaryPoint]:
    if not data_range.has_boundary:
        return []

    points: list[BoundaryPoint] = []
    step = _step(data_range)

    if data_range.min_value is not None:
        if data_range.min_inclusive:
            points.extend(
                [
                    _point(data_range, data_range.min_value - step, "min-1"),
                    _point(data_range, data_range.min_value, "min"),
                    _point(data_range, data_range.min_value + step, "min+1"),
                ]
            )
        else:
            points.extend(
                [
                    _point(data_range, data_range.min_value, "exclusive-min"),
                    _point(data_range, data_range.min_value + step, "exclusive-min+1"),
                    _point(data_range, data_range.min_value + (2 * step), "exclusive-min+2"),
                ]
            )

    if data_range.max_value is not None:
        if data_range.max_inclusive:
            points.extend(
                [
                    _point(data_range, data_range.max_value - step, "max-1"),
                    _point(data_range, data_range.max_value, "max"),
                    _point(data_range, data_range.max_value + step, "max+1"),
                ]
            )
        else:
            points.extend(
                [
                    _point(data_range, data_range.max_value - (2 * step), "exclusive-max-2"),
                    _point(data_range, data_range.max_value - step, "exclusive-max-1"),
                    _point(data_range, data_range.max_value, "exclusive-max"),
                ]
            )

    return _dedupe(points)


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
