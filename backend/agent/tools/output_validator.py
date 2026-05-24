from __future__ import annotations

from typing import Any


ALLOWED_TECHNIQUES = {"EP", "BVA", "DT"}


def require_fields(item: dict, fields: list[str], item_name: str) -> None:
    """检查单个 dict 是否包含必需字段，错误中带短预览便于排查。"""

    missing_fields = [field for field in fields if field not in item]
    if missing_fields:
        preview = repr(item)[:300]
        raise ValueError(
            f"{item_name} missing required field(s): {', '.join(missing_fields)}. "
            f"Item preview: {preview}"
        )


def validate_items(items: list[dict], fields: list[str], item_name: str) -> None:
    """检查列表形态和元素类型，并逐项校验必需字段。"""

    if not isinstance(items, list):
        raise ValueError(f"{item_name} must be a list.")

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            preview = repr(item)[:300]
            raise ValueError(f"{item_name}[{index}] must be a dict. Item preview: {preview}")
        require_fields(item, fields, f"{item_name}[{index}]")


def validate_requirements(requirements: list[dict]) -> None:
    """校验 RequirementParseAgent 输出的 requirements。"""

    validate_items(
        requirements,
        ["requirement_id", "module", "raw_text", "description"],
        "requirements",
    )


def validate_analyzed_requirements(items: list[dict]) -> None:
    """校验 RequirementAnalysisAgent 输出的 analyzed_requirements。"""

    validate_items(
        items,
        [
            "requirement_id",
            "module",
            "description",
            "input_fields",
            "data_ranges",
            "conditions",
            "business_rules",
            "expected_action",
        ],
        "analyzed_requirements",
    )


def validate_coverage_goals(items: list[dict]) -> None:
    """校验 CoverageIdentificationAgent 输出的 coverage_goals。"""

    validate_items(
        items,
        [
            "coverage_goal_id",
            "requirement_id",
            "goal",
            "related_inputs",
            "related_conditions",
            "expected_action",
        ],
        "coverage_goals",
    )


def validate_coverage_items(items: list[dict]) -> None:
    """校验 TechniqueAssignmentAgent 输出的 coverage_items。"""

    validate_items(
        items,
        [
            "coverage_item_id",
            "coverage_goal_id",
            "requirement_id",
            "technique",
            "description",
            "conditions",
            "data_ranges",
            "input_fields",
            "expected_action",
            "strategy_rationale",
        ],
        "coverage_items",
    )
    _validate_techniques(items, "coverage_items")


def validate_test_design_specs(items: list[dict]) -> None:
    """校验 TestDesignSpecAgent 输出的 test_design_specs。"""

    validate_items(
        items,
        [
            "spec_id",
            "coverage_item_id",
            "requirement_id",
            "technique",
            "design_points",
            "standard_ref",
        ],
        "test_design_specs",
    )
    _validate_techniques(items, "test_design_specs")
    for index, item in enumerate(items):
        design_points = item.get("design_points")
        if not isinstance(design_points, list) or not design_points:
            preview = repr(item)[:300]
            raise ValueError(
                f"test_design_specs[{index}] design_points must be a non-empty list. "
                f"Item preview: {preview}"
            )


def validate_test_cases(items: list[dict]) -> None:
    """校验 TestCaseDraftAgent 输出的 test_cases。"""

    validate_items(
        items,
        [
            "test_id",
            "requirement_id",
            "coverage_item_id",
            "spec_id",
            "technique",
            "title",
            "preconditions",
            "input_data",
            "test_steps",
            "expected_result",
            "standard_ref",
            "status",
        ],
        "test_cases",
    )
    _validate_techniques(items, "test_cases")
    for index, item in enumerate(items):
        if not str(item.get("expected_result", "")).strip():
            preview = repr(item)[:300]
            raise ValueError(
                f"test_cases[{index}] expected_result must not be empty. "
                f"Item preview: {preview}"
            )
        if item.get("status") != "Draft":
            preview = repr(item)[:300]
            raise ValueError(
                f"test_cases[{index}] status must be Draft. Item preview: {preview}"
            )


def _validate_techniques(items: list[dict], item_name: str) -> None:
    """统一检查黑盒技术枚举值，只允许 EP/BVA/DT。"""

    for index, item in enumerate(items):
        technique = str(item.get("technique", ""))
        if technique not in ALLOWED_TECHNIQUES:
            preview = repr(item)[:300]
            raise ValueError(
                f"{item_name}[{index}] technique must be EP, BVA, or DT. "
                f"Item preview: {preview}"
            )
