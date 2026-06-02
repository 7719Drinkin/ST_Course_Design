from __future__ import annotations

from typing import Any

from ...core.models import FullPipelineResult
from .output_validator import (
    validate_analyzed_requirements,
    validate_coverage_goals,
    validate_coverage_items,
    validate_requirements,
    validate_risk_analysis,
    validate_test_cases,
    validate_test_design_specs,
)


def run_final_quality_gate(result: Any) -> None:
    """在对外返回前执行最终交付门禁。

    单个对象是否合法已经由 models.py 保证；这里只关心完整交付物是否齐备，
    以及测试用例是否能连回风险优先级。
    """

    artifacts = _coerce_result(result)

    _require_non_empty(artifacts.requirements, "requirements")
    _require_non_empty(artifacts.analyzed_requirements, "analyzed_requirements")
    _require_non_empty(artifacts.coverage_goals, "coverage_goals")
    _require_non_empty(artifacts.coverage_items, "coverage_items")
    _require_non_empty(artifacts.test_design_specs, "test_design_specs")
    _require_non_empty(artifacts.test_cases, "test_cases")

    requirement_by_id = _index_by_id(artifacts.requirements, "requirement_id")
    analyzed_requirement_by_id = _index_by_id(
        artifacts.analyzed_requirements,
        "requirement_id",
    )
    risk_by_requirement = _index_by_id(
        artifacts.risk_analysis,
        "requirement_id",
    )
    coverage_goal_by_id = _index_by_id(
        artifacts.coverage_goals,
        "coverage_goal_id",
    )
    coverage_item_by_id = _index_by_id(
        artifacts.coverage_items,
        "coverage_item_id",
    )
    spec_by_id = _index_by_id(
        artifacts.test_design_specs,
        "spec_id",
    )

    # requirements -> analyzed_requirements
    for index, item in enumerate(artifacts.analyzed_requirements):
        _require_existing(
            item.requirement_id,
            requirement_by_id,
            f"analyzed_requirements[{index}].requirement_id not found in requirements.",
        )

    # analyzed_requirements -> risk_analysis
    for index, item in enumerate(artifacts.risk_analysis):
        _require_existing(
            item.requirement_id,
            analyzed_requirement_by_id,
            f"risk_analysis[{index}].requirement_id not found in analyzed_requirements.",
        )

    # analyzed_requirements -> coverage_goals
    for index, goal in enumerate(artifacts.coverage_goals):
        _require_existing(
            goal.requirement_id,
            analyzed_requirement_by_id,
            f"coverage_goals[{index}].requirement_id not found in analyzed_requirements.",
        )

    # coverage_goals -> coverage_items
    for index, item in enumerate(artifacts.coverage_items):
        _require_existing(
            item.coverage_goal_id,
            coverage_goal_by_id,
            f"coverage_items[{index}].coverage_goal_id not found in coverage_goals.",
        )
        _require_existing(
            item.requirement_id,
            analyzed_requirement_by_id,
            f"coverage_items[{index}].requirement_id not found in analyzed_requirements.",
        )

    # coverage_items -> test_design_specs
    for index, spec in enumerate(artifacts.test_design_specs):
        _require_existing(
            spec.coverage_item_id,
            coverage_item_by_id,
            f"test_design_specs[{index}].coverage_item_id not found in coverage_items.",
        )
        _require_existing(
            spec.requirement_id,
            analyzed_requirement_by_id,
            f"test_design_specs[{index}].requirement_id not found in analyzed_requirements.",
        )

    # test_design_specs -> test_cases, risk_analysis.test_priority -> test_cases.priority
    for index, test_case in enumerate(artifacts.test_cases):
        _require_existing(
            test_case.coverage_item_id,
            coverage_item_by_id,
            f"test_cases[{index}].coverage_item_id not found in coverage_items.",
        )
        _require_existing(
            test_case.spec_id,
            spec_by_id,
            f"test_cases[{index}].spec_id does not exist in test_design_specs.",
        )
        _require_existing(
            test_case.requirement_id,
            analyzed_requirement_by_id,
            f"test_cases[{index}].requirement_id not found in analyzed_requirements.",
        )
        risk_item = _require_existing(
            test_case.requirement_id,
            risk_by_requirement,
            f"test_cases[{index}].requirement_id has no RiskAnalysisItem.",
        )
        if test_case.priority != risk_item.test_priority:
            raise ValueError(
                f"test_cases[{index}].priority must match RiskAnalysisItem.test_priority."
            )


def _coerce_result(result: Any) -> FullPipelineResult:
    """把 dict/AgentContext/FullPipelineResult 统一恢复为强类型完整结果。"""

    if isinstance(result, FullPipelineResult):
        return result

    return FullPipelineResult(
        requirements=validate_requirements(_get_collection(result, "requirements")),
        analyzed_requirements=validate_analyzed_requirements(
            _get_collection(result, "analyzed_requirements")
        ),
        risk_analysis=validate_risk_analysis(_get_collection(result, "risk_analysis")),
        coverage_goals=validate_coverage_goals(_get_collection(result, "coverage_goals")),
        coverage_items=validate_coverage_items(_get_collection(result, "coverage_items")),
        test_design_specs=validate_test_design_specs(
            _get_collection(result, "test_design_specs")
        ),
        test_cases=validate_test_cases(_get_collection(result, "test_cases")),
    )


def _get_collection(result: Any, field: str) -> Any:
    if isinstance(result, dict):
        return result.get(field, [])
    return getattr(result, field, [])


def _index_by_id(items: list[Any], field: str) -> dict[str, Any]:
    # 重复 ID 属于 traceability_checker 的职责；final gate 这里只建索引用于存在性检查。
    return {str(getattr(item, field)): item for item in items}


def _require_non_empty(items: list[Any], item_name: str) -> None:
    if not items:
        raise ValueError(f"{item_name} must not be empty.")


def _require_existing(value: str, valid_items: dict[str, Any], message: str) -> Any:
    if value not in valid_items:
        raise ValueError(f"{message}: {value}")
    return valid_items[value]
