from __future__ import annotations

import re
from typing import Any


REQ_ID_RE = re.compile(r"^REQ-AUT-\d{3}$")
CG_ID_RE = re.compile(r"^CG-AUT-\d{3}-\d{3}$")
COV_ID_RE = re.compile(r"^COV-AUT-(?!CG-)[A-Z0-9-]+$")
SPEC_ID_RE = re.compile(r"^SPEC-AUT-[A-Z0-9-]+$")
TC_ID_RE = re.compile(r"^TC-AUT-[A-Z0-9-]+$")


def require_pipeline_id_formats(context: Any) -> None:
    require_id_format(_list(context, "requirements"), "requirement_id", REQ_ID_RE, "requirements")
    require_id_format(
        _list(context, "analyzed_requirements"),
        "requirement_id",
        REQ_ID_RE,
        "analyzed_requirements",
    )
    require_id_format(
        _list(context, "risk_analysis"),
        "requirement_id",
        REQ_ID_RE,
        "risk_analysis",
    )
    require_id_format(_list(context, "coverage_goals"), "coverage_goal_id", CG_ID_RE, "coverage_goals")
    require_id_format(
        _list(context, "coverage_items"),
        "coverage_item_id",
        COV_ID_RE,
        "coverage_items",
    )
    require_no_bad_coverage_ids(_list(context, "coverage_items"), "coverage_items")
    require_id_format(
        _list(context, "test_design_specs"),
        "spec_id",
        SPEC_ID_RE,
        "test_design_specs",
    )
    require_id_format(_list(context, "test_cases"), "test_id", TC_ID_RE, "test_cases")
    require_id_format(_list(context, "fsm_test_cases"), "test_id", TC_ID_RE, "fsm_test_cases")
    require_id_format(_list(context, "oracle_results"), "test_id", TC_ID_RE, "oracle_results")


def require_id_format(
    items: list[Any],
    field: str,
    pattern: re.Pattern[str],
    label: str,
) -> None:
    for index, item in enumerate(items):
        item_id = str(_get(item, field) or "")
        if not item_id:
            raise ValueError(f"{label}[{index}].{field} is missing.")
        if not pattern.fullmatch(item_id):
            raise ValueError(f"{label}[{index}].{field} has invalid format: {item_id}")


def require_unique_ids(items: list[Any], field: str, label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        item_id = str(_get(item, field) or "")
        if item_id in seen:
            duplicates.add(item_id)
        if item_id:
            seen.add(item_id)
    if duplicates:
        raise ValueError(f"{label}.{field} contains duplicate IDs: {sorted(duplicates)}")


def require_no_bad_coverage_ids(items: list[Any], label: str) -> None:
    bad_ids = sorted(
        item_id
        for item_id in (str(_get(item, "coverage_item_id") or "") for item in items)
        if item_id.startswith("COV-CG-") or "-CG-AUT-" in item_id
    )
    if bad_ids:
        raise ValueError(f"{label}.coverage_item_id contains invalid COV-CG IDs: {bad_ids}")


def _list(context: Any, field: str) -> list[Any]:
    value = context.get(field, []) if isinstance(context, dict) else getattr(context, field, [])
    return value if isinstance(value, list) else []


def _get(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field, "")
    return getattr(item, field, "")
