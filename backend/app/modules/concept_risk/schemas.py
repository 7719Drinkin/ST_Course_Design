"""Step 2 schemas — 概念识别与风险评分相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..intake_parse.schemas import FlexibleModel, ParsedRequirement, PromptEvidence, Requirement


# 业务概念（对象、操作、状态、约束）
class Concept(FlexibleModel):
    concept_id: str
    requirement_id: str
    name: str
    type: Literal["object", "operation", "state", "constraint"]
    evidence: str


# 风险评分对象（需求或覆盖项）
class RiskTarget(FlexibleModel):
    target_id: str
    target_type: Literal["requirement", "coverage_item"]
    text: str = ""


# 单条风险评分结果
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


# POST /concepts 请求体
class ConceptsRequest(FlexibleModel):
    session_id: str
    requirement_ids: list[str] | None = None
    parsed_requirements: list[ParsedRequirement] | None = None
    requirements: list[Requirement] | None = None
    include_evidence: bool = True


# POST /concepts 响应体
class ConceptsResponse(FlexibleModel):
    session_id: str
    concepts: list[Concept]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


# POST /risk 请求体
class RiskRequest(FlexibleModel):
    session_id: str
    targets: list[RiskTarget] = Field(default_factory=list)
    requirement_ids: list[str] | None = None
    risk_matrix_version: str | None = None


# POST /risk 响应体
class RiskResponse(FlexibleModel):
    session_id: str
    risk_results: list[RiskResult]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)
