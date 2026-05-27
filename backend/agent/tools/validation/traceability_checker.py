from __future__ import annotations

from typing import Any


def check_traceability(context: Any) -> None:
    """检查更细粒度的追溯链一致性。

    final_quality_gate 负责“引用是否存在”和“交付物是否齐备”；
    这里专注于重复 ID 和同一条 requirement 链是否被串错。
    如果某个引用缺失，本函数先跳过，留给 final_quality_gate 报更明确的缺失错误。
    """

    requirements = _list(context, "requirements")
    analyzed_requirements = _list(context, "analyzed_requirements")
    risk_analysis = _list(context, "risk_analysis")
    coverage_goals = _list(context, "coverage_goals")
    coverage_items = _list(context, "coverage_items")
    test_design_specs = _list(context, "test_design_specs")
    test_cases = _list(context, "test_cases")

    _index_unique(requirements, "requirement_id", "requirements")
    _index_unique(analyzed_requirements, "requirement_id", "analyzed_requirements")
    _index_unique(risk_analysis, "requirement_id", "risk_analysis")
    goals_by_id = _index_unique(coverage_goals, "coverage_goal_id", "coverage_goals")
    items_by_id = _index_unique(coverage_items, "coverage_item_id", "coverage_items")
    specs_by_id = _index_unique(test_design_specs, "spec_id", "test_design_specs")

    for index, item in enumerate(coverage_items):
        goal = goals_by_id.get(str(_get(item, "coverage_goal_id")))
        if goal is None:
            continue
        _require_same_requirement(
            _get(item, "requirement_id"),
            _get(goal, "requirement_id"),
            f"coverage_items[{index}] must stay on the same requirement as its CoverageGoal.",
        )

    for index, spec in enumerate(test_design_specs):
        coverage_item = items_by_id.get(str(_get(spec, "coverage_item_id")))
        if coverage_item is None:
            continue
        _require_same_requirement(
            _get(spec, "requirement_id"),
            _get(coverage_item, "requirement_id"),
            f"test_design_specs[{index}] must stay on the same requirement as its CoverageItem.",
        )

    for index, test_case in enumerate(test_cases):
        coverage_item = items_by_id.get(str(_get(test_case, "coverage_item_id")))
        if coverage_item is not None:
            _require_same_requirement(
                _get(test_case, "requirement_id"),
                _get(coverage_item, "requirement_id"),
                f"test_cases[{index}] must stay on the same requirement as its CoverageItem.",
            )

        spec = specs_by_id.get(str(_get(test_case, "spec_id")))
        if spec is None:
            continue
        _require_same_requirement(
            _get(test_case, "requirement_id"),
            _get(spec, "requirement_id"),
            f"test_cases[{index}] must stay on the same requirement as its TestDesignSpec.",
        )
        if str(_get(test_case, "coverage_item_id")) != str(_get(spec, "coverage_item_id")):
            raise ValueError(
                f"test_cases[{index}].coverage_item_id must match its TestDesignSpec."
            )


def _list(context: Any, field: str) -> list[Any]:
    if isinstance(context, dict):
        value = context.get(field, [])
    else:
        value = getattr(context, field, [])
    return value if isinstance(value, list) else []


def _index_unique(items: list[Any], field: str, item_name: str) -> dict[str, Any]:
    """建立 ID 索引并检查重复 ID，缺失 ID 由模型和 final gate 兜底。"""

    indexed: dict[str, Any] = {}
    for index, item in enumerate(items):
        item_id = str(_get(item, field) or "")
        if not item_id:
            continue
        if item_id in indexed:
            raise ValueError(f"{item_name}[{index}].{field} is duplicated: {item_id}")
        indexed[item_id] = item
    return indexed


def _require_same_requirement(left: Any, right: Any, message: str) -> None:
    if str(left) != str(right):
        raise ValueError(f"{message}: {left} != {right}")


def _get(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field, "")
    return getattr(item, field, "")
