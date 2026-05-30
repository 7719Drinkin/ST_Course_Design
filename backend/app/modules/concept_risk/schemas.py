"""Step 2 schemas — 风险评分相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..intake_parse.schemas import AnalyzedRequirement, FlexibleModel, PromptRecord


# 风险评分结果（辅助端点 optimize / export 使用）
class RiskResult(FlexibleModel):
    target_id: str
    target_type: Literal["requirement", "coverage_item"]
    impact: float
    likelihood: float
    risk_score: float
    risk_level: Literal["Low", "Medium", "High"]
    test_priority: Literal["P1", "P2", "P3"]
    reason: str
    evidence: list[str] = Field(default_factory=list)


# RiskAnalysisAgent 产物：单条风险分析项
class RiskAnalysisItem(FlexibleModel):
    requirement_id: str
    impact: int
    likelihood: int
    risk_score: int
    risk_level: Literal["High", "Medium", "Low"]
    test_priority: Literal["P1", "P2", "P3"]
    risk_reason: str


# POST /risk 请求体
class RiskRequest(FlexibleModel):
    session_id: str = "SESSION-CURRENT"
    requirement_text: str = ""
    analyzed_requirements: list[AnalyzedRequirement] = Field(default_factory=list)
    rag_context: str | None = None


# POST /risk 响应体
class RiskResponse(FlexibleModel):
    risk_analysis: list[RiskAnalysisItem]
    prompts_used: list[PromptRecord] = Field(default_factory=list)
