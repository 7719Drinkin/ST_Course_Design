from __future__ import annotations

from typing import Any
import re

from .models import DEFAULT_RISK_LEVEL, DEFAULT_STANDARD_REF, DataRange, ParsedRequirement


def parse_requirement(
    requirement_id: str,
    requirement_text: str,
    context: dict[str, Any] | None = None,
) -> ParsedRequirement:
    context = context or {}
    selected = _select_requirement_context(requirement_id, context)
    coverage_contexts = _coverage_item_contexts(requirement_id, context)

    input_fields = _unique(
        _as_list(selected.get("input_fields"))
        + _as_list(context.get("input_fields"))
        + [field for item in coverage_contexts for field in _as_list(item.get("input_fields"))]
    )
    raw_ranges = (
        _as_list(selected.get("data_ranges"))
        + _as_list(context.get("data_ranges"))
        + [item for coverage in coverage_contexts for item in _as_list(coverage.get("data_ranges"))]
    )
    data_ranges = parse_data_ranges(raw_ranges, input_fields)
    range_fields = [item.field for item in data_ranges if item.field]
    input_fields = _unique(input_fields + range_fields)

    conditions = _unique(
        _as_list(selected.get("conditions"))
        + _as_list(context.get("conditions"))
        + [condition for item in coverage_contexts for condition in _as_list(item.get("conditions"))]
        + _infer_conditions(requirement_text)
    )
    if not conditions:
        conditions = ["Requirement preconditions are satisfied"]

    expected_action = (
        selected.get("expected_action")
        or context.get("expected_action")
        or _first_coverage_value(coverage_contexts, "expected_action")
        or _infer_expected_action(requirement_text)
    )

    return ParsedRequirement(
        requirement_id=requirement_id,
        text=requirement_text,
        input_fields=input_fields,
        data_ranges=data_ranges,
        conditions=conditions,
        expected_action=expected_action,
        risk_level=_risk_level(requirement_id, selected, context),
        standard_ref=str(
            selected.get("standard_ref")
            or context.get("standard_ref")
            or DEFAULT_STANDARD_REF
        ),
    )


def parse_data_ranges(raw_ranges: list[Any], known_fields: list[str] | None = None) -> list[DataRange]:
    ranges: list[DataRange] = []
    for raw_range in raw_ranges:
        parsed = _parse_data_range(raw_range, known_fields or [])
        if parsed and parsed.field:
            ranges.append(parsed)
    return ranges


def _select_requirement_context(requirement_id: str, context: dict[str, Any]) -> dict[str, Any]:
    for key in ("parsed_requirement", "requirement"):
        value = context.get(key)
        if isinstance(value, dict):
            return value

    for key in ("parsed_requirements", "requirements"):
        items = context.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and str(item.get("requirement_id") or item.get("id")) == requirement_id:
                    return item
    return {}


def _coverage_item_contexts(requirement_id: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    items = context.get("coverage_items")
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("requirement_id")) == requirement_id
    ]


def _parse_data_range(raw_range: Any, known_fields: list[str]) -> DataRange | None:
    if isinstance(raw_range, dict):
        field = str(
            raw_range.get("field")
            or raw_range.get("name")
            or raw_range.get("input")
            or _first_known_field(known_fields)
            or ""
        )
        source = str(raw_range)
        return DataRange(
            field=field,
            min_value=_number(_first_present(raw_range, ["min", "min_value", "lower_bound"])),
            max_value=_number(_first_present(raw_range, ["max", "max_value", "upper_bound"])),
            min_inclusive=bool(raw_range.get("min_inclusive", True)),
            max_inclusive=bool(raw_range.get("max_inclusive", True)),
            data_type=str(raw_range.get("type") or raw_range.get("data_type") or "integer"),
            source=source,
        )

    text = str(raw_range).strip()
    if not text:
        return None

    field, expression = _split_field_expression(text, known_fields)
    data_type = "integer" if re.search(r"\b(int|integer|copies|count|id|year|number)\b", text, re.I) else "number"
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_inclusive = True
    max_inclusive = True

    between_match = re.search(r"between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)", expression, re.I)
    if between_match:
        min_value = _number(between_match.group(1))
        max_value = _number(between_match.group(2))

    closed_match = re.search(r"(-?\d+(?:\.\d+)?)\s*<=\s*[\w. -]+\s*<=\s*(-?\d+(?:\.\d+)?)", expression)
    if closed_match:
        min_value = _number(closed_match.group(1))
        max_value = _number(closed_match.group(2))

    range_match = re.search(r"\b(-?\d+(?:\.\d+)?)\s*[-~]\s*(-?\d+(?:\.\d+)?)\b", expression)
    if range_match and min_value is None and max_value is None:
        min_value = _number(range_match.group(1))
        max_value = _number(range_match.group(2))

    min_match = re.search(r"\bmin(?:imum)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)", expression, re.I)
    max_match = re.search(r"\bmax(?:imum)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)", expression, re.I)
    if min_match:
        min_value = _number(min_match.group(1))
    if max_match:
        max_value = _number(max_match.group(1))

    greater_match = re.search(r">\s*(-?\d+(?:\.\d+)?)", expression)
    greater_equal_match = re.search(r">=\s*(-?\d+(?:\.\d+)?)", expression)
    less_match = re.search(r"<\s*(-?\d+(?:\.\d+)?)", expression)
    less_equal_match = re.search(r"<=\s*(-?\d+(?:\.\d+)?)", expression)
    if greater_equal_match:
        min_value = _number(greater_equal_match.group(1))
        min_inclusive = True
    elif greater_match:
        min_value = _number(greater_match.group(1))
        min_inclusive = False
    if less_equal_match and not closed_match:
        max_value = _number(less_equal_match.group(1))
        max_inclusive = True
    elif less_match:
        max_value = _number(less_match.group(1))
        max_inclusive = False

    boundary_match = re.search(r"\b(-?\d+(?:\.\d+)?)\s+boundary\b", expression, re.I)
    if boundary_match and min_value is None and max_value is None:
        value = _number(boundary_match.group(1))
        min_value = value
        max_value = value

    return DataRange(
        field=field or _first_known_field(known_fields) or "value",
        min_value=min_value,
        max_value=max_value,
        min_inclusive=min_inclusive,
        max_inclusive=max_inclusive,
        data_type=data_type,
        source=text,
    )


def _split_field_expression(text: str, known_fields: list[str]) -> tuple[str, str]:
    if ":" in text:
        field, expression = text.split(":", 1)
        return field.strip(), expression.strip()

    for field in known_fields:
        if field and re.search(rf"\b{re.escape(field)}\b", text):
            return field, text
    return "", text


def _infer_conditions(requirement_text: str) -> list[str]:
    match = re.search(r"\bwhen\b(.+?)(?:\.|$)", requirement_text, re.I)
    if not match:
        match = re.search(r"\bif\b(.+?)(?:\.|$)", requirement_text, re.I)
    if not match:
        return []
    fragment = match.group(1)
    return [
        item.strip(" ,.;")
        for item in re.split(r"\band\b|,", fragment)
        if item.strip(" ,.;")
    ]


def _infer_expected_action(requirement_text: str) -> str:
    text = requirement_text.strip()
    if not text:
        return "The system follows the requirement's expected behavior."
    return text


def _risk_level(requirement_id: str, selected: dict[str, Any], context: dict[str, Any]) -> int:
    for key in ("risk_level", "risk_score"):
        if selected.get(key) is not None:
            return _to_int(selected.get(key), DEFAULT_RISK_LEVEL)
        if context.get(key) is not None:
            return _to_int(context.get(key), DEFAULT_RISK_LEVEL)

    risk_scores = context.get("risk_scores")
    if isinstance(risk_scores, dict) and risk_scores.get(requirement_id) is not None:
        return _to_int(risk_scores.get(requirement_id), DEFAULT_RISK_LEVEL)

    priority = str(selected.get("priority") or context.get("priority") or "").lower()
    if priority == "high":
        return 5
    if priority == "low":
        return 1
    return DEFAULT_RISK_LEVEL


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _unique(items: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _first_known_field(known_fields: list[str]) -> str:
    return next((field for field in known_fields if field), "")


def _first_coverage_value(items: list[dict[str, Any]], key: str) -> Any:
    for item in items:
        if item.get(key):
            return item[key]
    return None


def _first_present(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
