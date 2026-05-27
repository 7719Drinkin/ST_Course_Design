"""Step 3 schemas — 覆盖目标识别与策略分配相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ..concept_risk.schemas import RiskAnalysisItem
from ..intake_parse.schemas import AnalyzedRequirement, FlexibleModel, PromptRecord


# CoverageIdentificationAgent 产物：业务覆盖目标
class CoverageGoal(FlexibleModel):
    coverage_goal_id: str          # CG-AUT-*
    requirement_id: str            # 来源需求
    goal: str                      # 覆盖目标描述
    related_inputs: list[str] = Field(default_factory=list)
    related_conditions: list[str] = Field(default_factory=list)
    expected_action: str = ""


# TechniqueAssignmentAgent 产物：已分配单一黑盒测试技术的覆盖项
class CoverageItem(FlexibleModel):
    coverage_item_id: str          # COV-AUT-*
    coverage_goal_id: str = ""     # 来源覆盖目标
    requirement_id: str            # 来源需求
    technique: Literal["EP", "BVA", "DT", "FSM"]
    description: str = ""
    conditions: list[str] = Field(default_factory=list)
    data_ranges: list[str] = Field(default_factory=list)
    input_fields: list[str] = Field(default_factory=list)
    expected_action: str = ""
    strategy_rationale: str = ""
    technique_reason: str = ""


# 测试策略（辅助端点 analysis / export 使用）
class Strategy(FlexibleModel):
    strategy_id: str
    coverage_item_id: str
    technique: Literal["EP", "BVA", "DT", "FSM"]
    standard_ref: str
    reason: str
    algorithm_params: dict[str, Any] = Field(default_factory=dict)


# POST /coverage 请求体
class CoverageRequest(FlexibleModel):
    analyzed_requirements: list[AnalyzedRequirement]
    risk_analysis: list[RiskAnalysisItem]


# POST /coverage 响应体
class CoverageResponse(FlexibleModel):
    coverage_goals: list[CoverageGoal]
    prompts_used: list[PromptRecord] = Field(default_factory=list)


# POST /strategy 请求体
class StrategyRequest(FlexibleModel):
    coverage_goals: list[CoverageGoal]
    analyzed_requirements: list[AnalyzedRequirement]
    risk_analysis: list[RiskAnalysisItem]


# POST /strategy 响应体
class StrategyResponse(FlexibleModel):
    coverage_items: list[CoverageItem]
    prompts_used: list[PromptRecord] = Field(default_factory=list)
