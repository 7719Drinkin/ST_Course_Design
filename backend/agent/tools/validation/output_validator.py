from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ...core.models import (
    AgentModel,
    AnalyzedRequirement,
    CoverageGoal,
    CoverageItem,
    FsmGenerationResult,
    ParsedRequirement,
    RiskAnalysisItem,
    TestCaseDraft,
    TestDesignSpec,
)


T = TypeVar("T", bound=AgentModel)


def validate_model(item: Any, model_cls: type[T], item_name: str) -> T:
    """把单个 LLM 输出对象转换为强类型模型，并包装 Pydantic 错误。"""

    if isinstance(item, model_cls):
        return item

    raw_item = _as_dict(item)
    if raw_item is None:
        preview = repr(item)[:300]
        raise ValueError(
            f"{item_name} must be a dict or {model_cls.__name__}. Item preview: {preview}"
        )

    try:
        return model_cls.model_validate(raw_item)
    except ValidationError as exc:
        raise ValueError(_format_validation_error(item_name, None, raw_item, exc)) from exc


def validate_model_list(items: Any, model_cls: type[T], item_name: str) -> list[T]:
    """把 LLM 返回的 list/dict item 统一转换为内部强类型模型列表。"""

    if not isinstance(items, list):
        preview = repr(items)[:300]
        raise ValueError(f"{item_name} must be a list. Item preview: {preview}")

    validated_items: list[T] = []
    for index, item in enumerate(items):
        try:
            validated_items.append(validate_model(item, model_cls, f"{item_name}[{index}]"))
        except ValueError as exc:
            preview = repr(item)[:300]
            message = str(exc)
            if "Item preview:" not in message:
                message = f"{message}. Item preview: {preview}"
            raise ValueError(message) from exc

    return validated_items


def validate_requirements(items: Any) -> list[ParsedRequirement]:
    """校验并转换 RequirementParseAgent 输出。"""

    return validate_model_list(items, ParsedRequirement, "requirements")


def validate_analyzed_requirements(items: Any) -> list[AnalyzedRequirement]:
    """校验并转换 RequirementAnalysisAgent 输出。"""

    return validate_model_list(items, AnalyzedRequirement, "analyzed_requirements")


def validate_risk_analysis(items: Any) -> list[RiskAnalysisItem]:
    """校验并转换 RiskAnalysisAgent 输出。"""

    return validate_model_list(items, RiskAnalysisItem, "risk_analysis")


def validate_coverage_goals(items: Any) -> list[CoverageGoal]:
    """校验并转换 CoverageIdentificationAgent 输出。"""

    return validate_model_list(items, CoverageGoal, "coverage_goals")


def validate_coverage_items(items: Any) -> list[CoverageItem]:
    """校验并转换 TechniqueAssignmentAgent 输出。"""

    return validate_model_list(items, CoverageItem, "coverage_items")


def validate_test_design_specs(items: Any) -> list[TestDesignSpec]:
    """校验并转换 TestDesignSpecAgent 输出。"""

    return validate_model_list(items, TestDesignSpec, "test_design_specs")


def validate_test_cases(items: Any) -> list[TestCaseDraft]:
    """校验并转换 TestCaseDraftAgent 输出。"""

    return validate_model_list(items, TestCaseDraft, "test_cases")


def validate_fsm_generation(item: Any) -> FsmGenerationResult:
    """校验并转换 FR4 FSM 建模 prompt 的输出。"""

    return validate_model(item, FsmGenerationResult, "fsm_generation")


def _as_dict(item: Any) -> dict[str, Any] | None:
    if isinstance(item, BaseModel):
        return item.model_dump()
    if isinstance(item, dict):
        return item
    return None


def _format_validation_error(
    item_name: str,
    index: int | None,
    item: dict[str, Any],
    exc: ValidationError,
) -> str:
    preview = repr(item)[:300]
    issues = "; ".join(_format_issue(error) for error in exc.errors())
    prefix = item_name if index is None else f"{item_name}[{index}]"
    return (
        f"{prefix} validation failed: {issues}. "
        f"Item preview: {preview}"
    )


def _format_issue(error: dict[str, Any]) -> str:
    location = ".".join(str(part) for part in error.get("loc", ())) or "__root__"
    return f"{location}: {error.get('msg', 'validation error')}"
