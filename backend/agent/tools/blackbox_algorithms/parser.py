from __future__ import annotations

from typing import Any
import re

from .models import DEFAULT_RISK_LEVEL, DataRange, ParsedRequirement


def parse_requirement(
    requirement_id: str,
    requirement_text: str,
    context: dict[str, Any] | None = None,
) -> ParsedRequirement:
    context = context or {}
    selected = _select_requirement_context(requirement_id, context)
    coverage_contexts = _coverage_item_contexts(requirement_id, context)

    context_fields = _unique(
        _as_list(selected.get("input_fields"))
        + _as_list(context.get("input_fields"))
        + [field for item in coverage_contexts for field in _as_list(item.get("input_fields"))]
    )
    enum_values = _merge_enum_values(
        _enum_values_from_context(selected),
        _enum_values_from_context(context),
        _infer_enum_values(requirement_text),
    )
    inferred_text_ranges = infer_data_ranges_from_text(requirement_text, context_fields)
    raw_ranges = (
        _as_list(selected.get("data_ranges"))
        + _as_list(context.get("data_ranges"))
        + [item for coverage in coverage_contexts for item in _as_list(coverage.get("data_ranges"))]
    )
    data_ranges = _dedupe_ranges(parse_data_ranges(raw_ranges, context_fields) + inferred_text_ranges)
    input_fields = _unique(
        context_fields
        + _infer_input_fields(requirement_text)
        + [item.field for item in data_ranges]
        + list(enum_values)
    )

    business_rules = _unique(
        _as_list(selected.get("business_rules"))
        + _as_list(context.get("business_rules"))
    )
    conditions = _unique(
        _as_list(selected.get("conditions"))
        + _as_list(context.get("conditions"))
        + [condition for item in coverage_contexts for condition in _as_list(item.get("conditions"))]
        + business_rules
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
        enum_values=enum_values,
        conditions=conditions,
        business_rules=business_rules or conditions,
        expected_action=str(expected_action),
        risk_level=_risk_level(requirement_id, selected, context),
    )


def parse_data_ranges(raw_ranges: list[Any], known_fields: list[str] | None = None) -> list[DataRange]:
    ranges: list[DataRange] = []
    for raw_range in raw_ranges:
        parsed = _parse_data_range(raw_range, known_fields or [])
        if parsed and parsed.field:
            ranges.append(parsed)
    return ranges


def infer_data_ranges_from_text(requirement_text: str, known_fields: list[str] | None = None) -> list[DataRange]:
    text = requirement_text.strip()
    ranges: list[DataRange] = []

    patterns = [
        (
            re.compile(
                r"\b(?P<field>[A-Za-z_][\w.]*)\s+length\s+between\s+"
                r"(?P<min>-?\d+(?:\.\d+)?)\s+and\s+(?P<max>-?\d+(?:\.\d+)?)",
                re.I,
            ),
            lambda match: _range_from_match(match, field_suffix=".length"),
        ),
        (
            re.compile(
                r"\b(?P<field>[A-Za-z_][\w.]*)\s+length\s+"
                r"(?P<min>-?\d+(?:\.\d+)?)\s*[-~]\s*(?P<max>-?\d+(?:\.\d+)?)",
                re.I,
            ),
            lambda match: _range_from_match(match, field_suffix=".length"),
        ),
        (
            re.compile(
                r"\b(?P<field>[A-Za-z_][\w.]*)\s+between\s+"
                r"(?P<min>-?\d+(?:\.\d+)?)\s+and\s+(?P<max>-?\d+(?:\.\d+)?)",
                re.I,
            ),
            _range_from_match,
        ),
        (
            re.compile(
                r"\b(?P<field>[A-Za-z_][\w.]*)\s*>=\s*(?P<min>-?\d+(?:\.\d+)?)"
                r"\s*(?:and|,)\s*(?:[A-Za-z_][\w.]*\s*)?<=\s*(?P<max>-?\d+(?:\.\d+)?)",
                re.I,
            ),
            _range_from_match,
        ),
        (
            re.compile(
                r"\b(?P<field>[A-Za-z_][\w.]*)\s*<=\s*(?P<max>-?\d+(?:\.\d+)?)"
                r"\s*(?:and|,)\s*(?:[A-Za-z_][\w.]*\s*)?>=\s*(?P<min>-?\d+(?:\.\d+)?)",
                re.I,
            ),
            _range_from_match,
        ),
        (
            re.compile(r"\b(?P<field>[A-Za-z_][\w.]*)\s*>\s*(?P<min>-?\d+(?:\.\d+)?)", re.I),
            lambda match: _range_from_match(match, min_inclusive=False),
        ),
        (
            re.compile(r"\b(?P<field>[A-Za-z_][\w.]*)\s*>=\s*(?P<min>-?\d+(?:\.\d+)?)", re.I),
            _range_from_match,
        ),
        (
            re.compile(r"\b(?P<field>[A-Za-z_][\w.]*)\s*<\s*(?P<max>-?\d+(?:\.\d+)?)", re.I),
            lambda match: _range_from_match(match, max_inclusive=False),
        ),
        (
            re.compile(r"\b(?P<field>[A-Za-z_][\w.]*)\s*<=\s*(?P<max>-?\d+(?:\.\d+)?)", re.I),
            _range_from_match,
        ),
    ]

    occupied_spans: list[tuple[int, int]] = []
    for pattern, builder in patterns:
        for match in pattern.finditer(text):
            if _overlaps(match.span(), occupied_spans):
                continue
            ranges.append(builder(match))
            occupied_spans.append(match.span())

    return _dedupe_ranges(ranges)


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


def _overlaps(span: tuple[int, int], occupied_spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied_spans)


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
    inferred = infer_data_ranges_from_text(f"{field} {expression}".strip(), [field] if field else known_fields)
    if inferred:
        item = inferred[0]
        return DataRange(
            field=field or item.field,
            min_value=item.min_value,
            max_value=item.max_value,
            min_inclusive=item.min_inclusive,
            max_inclusive=item.max_inclusive,
            data_type=_data_type(text),
            source=text,
        )

    min_match = re.search(r"\bmin(?:imum)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)", expression, re.I)
    max_match = re.search(r"\bmax(?:imum)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)", expression, re.I)
    boundary_match = re.search(r"\b(-?\d+(?:\.\d+)?)\s+boundary\b", expression, re.I)
    min_value = _number(min_match.group(1)) if min_match else None
    max_value = _number(max_match.group(1)) if max_match else None
    if boundary_match and min_value is None and max_value is None:
        min_value = max_value = _number(boundary_match.group(1))

    return DataRange(
        field=field or _first_known_field(known_fields) or "value",
        min_value=min_value,
        max_value=max_value,
        data_type=_data_type(text),
        source=text,
    )


def _range_from_match(
    match: re.Match[str],
    field_suffix: str = "",
    min_inclusive: bool = True,
    max_inclusive: bool = True,
) -> DataRange:
    field = f"{match.group('field')}{field_suffix}"
    return DataRange(
        field=field,
        min_value=_number(match.groupdict().get("min")),
        max_value=_number(match.groupdict().get("max")),
        min_inclusive=min_inclusive,
        max_inclusive=max_inclusive,
        data_type=_data_type(match.group(0)),
        source=match.group(0),
    )


def _infer_input_fields(requirement_text: str) -> list[str]:
    fields: list[str] = []
    for pattern in [
        r"\bwhen\s+(?P<fields>[A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*(?:\s+and\s+[A-Za-z_][\w.]*)?)\s+are\s+submitted",
        r"\bwith\s+(?P<fields>[A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*(?:\s+and\s+[A-Za-z_][\w.]*)?)\s+(?:are\s+)?submitted",
    ]:
        for match in re.finditer(pattern, requirement_text, re.I):
            fields.extend(_split_fields(match.group("fields")))

    for match in re.finditer(r"\b([A-Za-z_][\w.]*)\s*(?:>=|<=|>|<|=)\s*-?\d+(?:\.\d+)?", requirement_text):
        fields.append(match.group(1))
    return _unique(fields)


def _infer_enum_values(requirement_text: str) -> dict[str, list[str]]:
    enum_values: dict[str, list[str]] = {}
    patterns = [
        r"\b(?P<field>[A-Za-z_][\w.]*)\s+(?:is|are|must be|can be)\s+one\s+of\s+(?P<values>[A-Za-z0-9_ ,/-]+)",
        r"\b(?P<field>[A-Za-z_][\w.]*)\s+in\s+\[(?P<values>[A-Za-z0-9_ ,/-]+)\]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, requirement_text, re.I):
            values = _split_fields(match.group("values"))
            if values:
                enum_values[match.group("field")] = values
    return enum_values


def _infer_conditions(requirement_text: str) -> list[str]:
    fragments: list[str] = []
    for pattern in [
        r"\bonly\s+if\b(?P<fragment>.+?)(?:\.|$)",
        r"\bunless\b(?P<fragment>.+?)(?:\.|$)",
        r"\bwhen\b(?P<fragment>.+?)(?:\.|$)",
        r"\bif\b(?P<fragment>.+?)(?:\.|$)",
    ]:
        for match in re.finditer(pattern, requirement_text, re.I):
            fragments.append(match.group("fragment"))

    conditions: list[str] = []
    for fragment in fragments:
        protected = re.sub(
            r"(between\s+-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)",
            r"\1 __BETWEEN_AND__ \2",
            fragment,
            flags=re.I,
        )
        for item in re.split(r"\band\b|\bor\b|,", protected, flags=re.I):
            condition = item.replace("__BETWEEN_AND__", "and").strip(" ,.;")
            if condition:
                conditions.append(condition)

    for match in re.finditer(r"\b[A-Za-z_][\w.]*\s*(?:>=|<=|>|<|=)\s*-?\d+(?:\.\d+)?", requirement_text):
        conditions.append(match.group(0))
    for match in re.finditer(r"\bnot\s+[A-Za-z_][\w. ]+", requirement_text, re.I):
        conditions.append(match.group(0).strip(" ,.;"))
    return _unique(conditions)


def _enum_values_from_context(context: dict[str, Any]) -> dict[str, list[str]]:
    raw = (
        context.get("enum_values")
        or context.get("enumerations")
        or context.get("allowed_values")
        or {}
    )
    if isinstance(raw, dict):
        return {str(field): _split_fields(values) for field, values in raw.items() if _split_fields(values)}
    return {}


def _merge_enum_values(*items: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for item in items:
        for field, values in item.items():
            merged[field] = _unique(merged.get(field, []) + values)
    return merged


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


def _dedupe_ranges(ranges: list[DataRange]) -> list[DataRange]:
    result: list[DataRange] = []
    seen: set[tuple[str, int | float | None, int | float | None, bool, bool]] = set()
    for item in ranges:
        key = (item.field, item.min_value, item.max_value, item.min_inclusive, item.max_inclusive)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _split_field_expression(text: str, known_fields: list[str]) -> tuple[str, str]:
    if ":" in text:
        field, expression = text.split(":", 1)
        return field.strip(), expression.strip()

    for field in known_fields:
        if field and re.search(rf"\b{re.escape(field)}\b", text):
            return field, text
    return "", text


def _split_fields(value: Any) -> list[str]:
    if isinstance(value, list):
        return _unique(value)
    if isinstance(value, tuple):
        return _unique(list(value))
    text = str(value)
    return _unique([item.strip() for item in re.split(r",|\band\b|/", text, flags=re.I)])


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


def _data_type(text: str) -> str:
    return "integer" if re.search(r"\b(int|integer|copies|count|id|year|number|length|age)\b", text, re.I) else "number"


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
