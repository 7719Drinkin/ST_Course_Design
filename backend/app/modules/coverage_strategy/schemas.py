"""Step 3 schemas — 覆盖项生成与策略分配相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ..concept_risk.schemas import Concept, RiskResult
from ..intake_parse.schemas import FlexibleModel, ParsedRequirement, PromptEvidence


# 覆盖项（一条需求中需要被测试验证的某个维度）
class CoverageItem(FlexibleModel):
    coverage_item_id: str
    requirement_id: str
    description: str
    technique: Literal["EP", "BVA", "DT", "FSM"]
    strategy: str = ""
    status: Literal["ai_generated", "human_revised", "human_added", "rejected"] = "ai_generated"
    source: Literal["llm", "algorithm", "designer"] = "algorithm"


# 测试策略（为覆盖项选择的具体测试技术和算法参数）
class Strategy(FlexibleModel):
    strategy_id: str
    coverage_item_id: str
    technique: Literal["EP", "BVA", "DT", "FSM"]
    standard_ref: str
    reason: str
    algorithm_params: dict[str, Any] = Field(default_factory=dict)


# POST /coverage 请求体
class CoverageRequest(FlexibleModel):
    session_id: str
    parsed_requirements: list[ParsedRequirement] | None = None
    concepts: list[Concept] | None = None
    risk_results: list[RiskResult] | None = None
    requirement_ids: list[str] | None = None


# POST /coverage 响应体
class CoverageResponse(FlexibleModel):
    session_id: str
    coverage_items: list[CoverageItem]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


# POST /strategy 请求体
class StrategyRequest(FlexibleModel):
    session_id: str
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    coverage_item_ids: list[str] | None = None
    risk_results: list[RiskResult] | None = None
    parsed_requirements: list[ParsedRequirement] | None = None


# POST /strategy 响应体
class StrategyResponse(FlexibleModel):
    session_id: str
    strategies: list[Strategy]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)
