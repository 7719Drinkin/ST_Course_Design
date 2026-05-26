from __future__ import annotations

import re
from typing import Any

from ...core.agent_context import AgentContext


def normalize_requirement_ids(requirements: list[Any]) -> list[Any]:
    """按列表顺序重写 requirement_id，适合单独测试该规则。"""

    for index, requirement in enumerate(requirements, start=1):
        _set(requirement, "requirement_id", f"REQ-AUT-{index:03d}")
    return requirements


def normalize_coverage_goal_ids(coverage_goals: list[Any]) -> list[Any]:
    """按 requirement 分组重写 coverage_goal_id。"""

    counters: dict[str, int] = {}
    for goal in coverage_goals:
        req_number = _requirement_number(str(_get(goal, "requirement_id")))
        counters[req_number] = counters.get(req_number, 0) + 1
        _set(goal, "coverage_goal_id", f"CG-AUT-{req_number}-{counters[req_number]:03d}")
    return coverage_goals


def normalize_coverage_item_ids(coverage_items: list[Any]) -> list[Any]:
    """按 requirement + technique 分组重写 coverage_item_id。"""

    counters: dict[tuple[str, str], int] = {}
    for item in coverage_items:
        req_number = _requirement_number(str(_get(item, "requirement_id")))
        technique = str(_get(item, "technique")).upper()
        key = (req_number, technique)
        counters[key] = counters.get(key, 0) + 1
        _set(item, "coverage_item_id", f"COV-AUT-{req_number}-{technique}-{counters[key]:03d}")
    return coverage_items


def normalize_spec_ids(test_design_specs: list[Any]) -> list[Any]:
    """按 requirement + technique 分组重写 spec_id。"""

    counters: dict[tuple[str, str], int] = {}
    for spec in test_design_specs:
        req_number = _requirement_number(str(_get(spec, "requirement_id")))
        technique = str(_get(spec, "technique")).upper()
        key = (req_number, technique)
        counters[key] = counters.get(key, 0) + 1
        _set(spec, "spec_id", f"SPEC-AUT-{req_number}-{technique}-{counters[key]:03d}")
    return test_design_specs


def normalize_test_case_ids(test_cases: list[Any]) -> list[Any]:
    """按 requirement 分组重写 test_id。"""

    counters: dict[str, int] = {}
    for test_case in test_cases:
        req_number = _requirement_number(str(_get(test_case, "requirement_id")))
        counters[req_number] = counters.get(req_number, 0) + 1
        _set(test_case, "test_id", f"TC-AUT-{req_number}-{counters[req_number]:03d}")
    return test_cases


def normalize_all_ids(context: AgentContext | Any) -> None:
    """统一规范化上下文中所有 ID，并同步所有跨层引用。

    这是推荐在 pipeline 收尾阶段调用的入口。它先重写上游 ID，
    再用映射逐层同步下游引用，避免 LLM 自行生成的 ID 造成断链。
    """

    # 必须先改最上游 requirement_id，再同步所有下游 requirement_id；
    # 如果先改 coverage/test case，后续就无法知道旧 ID 应该映射到哪里。
    req_map = _rewrite_requirement_ids(context.requirements)
    _apply_map(context.analyzed_requirements, "requirement_id", req_map)
    _apply_map(context.risk_analysis, "requirement_id", req_map)
    _apply_map(context.coverage_goals, "requirement_id", req_map)
    _apply_map(context.coverage_items, "requirement_id", req_map)
    _apply_map(context.test_design_specs, "requirement_id", req_map)
    _apply_map(context.test_cases, "requirement_id", req_map)

    # 覆盖目标 ID 改写后，只影响 coverage_items.coverage_goal_id。
    goal_map = _rewrite_coverage_goal_ids(context.coverage_goals)
    _apply_map(context.coverage_items, "coverage_goal_id", goal_map)

    # 覆盖项 ID 是 spec 和 test case 的共同外键，必须一次改写后同步两处。
    coverage_item_map = _rewrite_coverage_item_ids(context.coverage_items)
    _apply_map(context.test_design_specs, "coverage_item_id", coverage_item_map)
    _apply_map(context.test_cases, "coverage_item_id", coverage_item_map)

    # spec_id 只被 test case 引用，所以最后同步这一层。
    spec_map = _rewrite_spec_ids(context.test_design_specs)
    _apply_map(context.test_cases, "spec_id", spec_map)

    # test_id 没有下游引用，可以最后按稳定顺序重写。
    normalize_test_case_ids(context.test_cases)


def _rewrite_requirement_ids(requirements: list[Any]) -> dict[str, str]:
    """重写 requirements 的 ID，并返回 old_id -> new_id 映射。"""

    mapping: dict[str, str] = {}
    for index, requirement in enumerate(requirements, start=1):
        old_id = str(_get(requirement, "requirement_id"))
        new_id = f"REQ-AUT-{index:03d}"
        if old_id:
            mapping[old_id] = new_id
        _set(requirement, "requirement_id", new_id)
    return mapping


def _rewrite_coverage_goal_ids(coverage_goals: list[Any]) -> dict[str, str]:
    """重写 coverage_goals 的 ID，并返回 old_id -> new_id 映射。"""

    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}
    for goal in coverage_goals:
        old_id = str(_get(goal, "coverage_goal_id"))
        req_number = _requirement_number(str(_get(goal, "requirement_id")))
        counters[req_number] = counters.get(req_number, 0) + 1
        new_id = f"CG-AUT-{req_number}-{counters[req_number]:03d}"
        if old_id:
            mapping[old_id] = new_id
        _set(goal, "coverage_goal_id", new_id)
    return mapping


def _rewrite_coverage_item_ids(coverage_items: list[Any]) -> dict[str, str]:
    """重写 coverage_items 的 ID，并返回 old_id -> new_id 映射。"""

    mapping: dict[str, str] = {}
    counters: dict[tuple[str, str], int] = {}
    for item in coverage_items:
        old_id = str(_get(item, "coverage_item_id"))
        req_number = _requirement_number(str(_get(item, "requirement_id")))
        # technique 已经由模型校验过，这里只把它作为 ID 组成部分，不承担枚举校验。
        technique = str(_get(item, "technique")).upper()
        key = (req_number, technique)
        counters[key] = counters.get(key, 0) + 1
        new_id = f"COV-AUT-{req_number}-{technique}-{counters[key]:03d}"
        if old_id:
            mapping[old_id] = new_id
        _set(item, "coverage_item_id", new_id)
    return mapping


def _rewrite_spec_ids(test_design_specs: list[Any]) -> dict[str, str]:
    """重写 test_design_specs 的 ID，并返回 old_id -> new_id 映射。"""

    mapping: dict[str, str] = {}
    counters: dict[tuple[str, str], int] = {}
    for spec in test_design_specs:
        old_id = str(_get(spec, "spec_id"))
        req_number = _requirement_number(str(_get(spec, "requirement_id")))
        # technique 已经在 TestDesignSpec 中校验，这里只用于生成稳定 spec_id。
        technique = str(_get(spec, "technique")).upper()
        key = (req_number, technique)
        counters[key] = counters.get(key, 0) + 1
        new_id = f"SPEC-AUT-{req_number}-{technique}-{counters[key]:03d}"
        if old_id:
            mapping[old_id] = new_id
        _set(spec, "spec_id", new_id)
    return mapping


def _apply_map(items: list[Any], field: str, mapping: dict[str, str]) -> None:
    """把某个字段中的旧 ID 替换成规范化后的新 ID。"""

    for item in items:
        old_value = str(_get(item, field))
        if old_value in mapping:
            _set(item, field, mapping[old_value])


def _requirement_number(requirement_id: str) -> str:
    """从 requirement_id 中提取末尾数字，格式化为三位编号。"""

    match = re.search(r"(\d+)(?!.*\d)", requirement_id)
    if match:
        return f"{int(match.group(1)):03d}"
    return "000"


def _get(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field, "")
    return getattr(item, field, "")


def _set(item: Any, field: str, value: Any) -> None:
    if isinstance(item, dict):
        item[field] = value
    else:
        setattr(item, field, value)
