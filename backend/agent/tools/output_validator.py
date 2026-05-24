from __future__ import annotations

from typing import Any


ALLOWED_TECHNIQUES = {"EP", "BVA", "DT"}
ALLOWED_RISK_LEVELS = {"High", "Medium", "Low"}
ALLOWED_PRIORITIES = {"P1", "P2", "P3"}


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


def validate_risk_analysis(items: list[dict]) -> None:
    """校验 RiskAnalysisAgent 输出的 risk_analysis。"""

    validate_items(
        items,
        [
            "requirement_id",
            "impact",
            "likelihood",
            "risk_score",
            "risk_level",
            "test_priority",
            "risk_reason",
        ],
        "risk_analysis",
    )
    for index, item in enumerate(items):
        impact = item.get("impact")
        likelihood = item.get("likelihood")
        risk_score = item.get("risk_score")
        if not isinstance(impact, int) or not 1 <= impact <= 5:
            raise ValueError(f"risk_analysis[{index}] impact must be an integer from 1 to 5.")
        if not isinstance(likelihood, int) or not 1 <= likelihood <= 5:
            raise ValueError(f"risk_analysis[{index}] likelihood must be an integer from 1 to 5.")
        if risk_score != impact * likelihood:
            raise ValueError(f"risk_analysis[{index}] risk_score must equal impact * likelihood.")
        expected_level = "High" if risk_score >= 15 else "Medium" if risk_score >= 8 else "Low"
        expected_priority = {"High": "P1", "Medium": "P2", "Low": "P3"}[expected_level]
        if item.get("risk_level") not in ALLOWED_RISK_LEVELS:
            raise ValueError(f"risk_analysis[{index}] risk_level must be High, Medium, or Low.")
        if item.get("risk_level") != expected_level:
            raise ValueError(f"risk_analysis[{index}] risk_level does not match risk_score.")
        if item.get("test_priority") not in ALLOWED_PRIORITIES:
            raise ValueError(f"risk_analysis[{index}] test_priority must be P1, P2, or P3.")
        if item.get("test_priority") != expected_priority:
            raise ValueError(f"risk_analysis[{index}] test_priority does not match risk_level.")


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
            "technique_reason",
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
            "priority",
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
        if item.get("priority") not in ALLOWED_PRIORITIES:
            preview = repr(item)[:300]
            raise ValueError(
                f"test_cases[{index}] priority must be P1, P2, or P3. "
                f"Item preview: {preview}"
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
