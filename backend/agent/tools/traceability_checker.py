from __future__ import annotations

from ..core.agent_context import AgentContext


def check_traceability(context: AgentContext) -> None:
    """检查从需求到测试用例的全链路 ID 引用是否连续。"""

    requirement_ids = _ids(context.requirements, "requirement_id")
    analyzed_requirement_ids = _ids(context.analyzed_requirements, "requirement_id")
    coverage_goal_ids = _ids(context.coverage_goals, "coverage_goal_id")
    coverage_item_ids = _ids(context.coverage_items, "coverage_item_id")
    test_design_spec_ids = _ids(context.test_design_specs, "spec_id")

    for item in context.analyzed_requirements:
        _require_link(
            item.get("requirement_id"),
            requirement_ids,
            "analyzed_requirement.requirement_id not found in requirements",
        )

    for item in context.coverage_goals:
        _require_link(
            item.get("requirement_id"),
            analyzed_requirement_ids,
            "coverage_goal.requirement_id not found in analyzed_requirements",
        )

    for item in context.coverage_items:
        _require_link(
            item.get("requirement_id"),
            analyzed_requirement_ids,
            "coverage_item.requirement_id not found in analyzed_requirements",
        )
        _require_link(
            item.get("coverage_goal_id"),
            coverage_goal_ids,
            "coverage_item.coverage_goal_id not found in coverage_goals",
        )

    for item in context.test_design_specs:
        _require_link(
            item.get("coverage_item_id"),
            coverage_item_ids,
            "test_design_spec.coverage_item_id not found in coverage_items",
        )
        _require_link(
            item.get("requirement_id"),
            analyzed_requirement_ids,
            "test_design_spec.requirement_id not found in analyzed_requirements",
        )

    for item in context.test_cases:
        _require_link(
            item.get("coverage_item_id"),
            coverage_item_ids,
            "test_case.coverage_item_id not found in coverage_items",
        )
        _require_link(
            item.get("spec_id"),
            test_design_spec_ids,
            "test_case.spec_id not found in test_design_specs",
        )
        _require_link(
            item.get("requirement_id"),
            analyzed_requirement_ids,
            "test_case.requirement_id not found in analyzed_requirements",
        )


def _ids(items: list[dict], field: str) -> set[str]:
    """从对象列表中收集指定 ID 字段。"""

    return {str(item.get(field, "")) for item in items if isinstance(item, dict)}


def _require_link(value: object, valid_ids: set[str], message: str) -> None:
    """断言单个引用值存在于目标 ID 集合中。"""

    normalized_value = str(value or "")
    if normalized_value not in valid_ids:
        raise ValueError(f"{message}: {normalized_value}")
