"""Step 4 schemas — 测试用例生成、FSM 状态迁移、Oracle 审查相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ..concept_risk.schemas import RiskResult
from ..coverage_strategy.schemas import CoverageItem, Strategy
from ..intake_parse.schemas import FlexibleModel, ParsedRequirement, PromptEvidence, Requirement


# 测试用例
class TestCase(FlexibleModel):
    test_id: str
    requirement_id: str
    coverage_item_id: str
    strategy_id: str
    technique: Literal["EP", "BVA", "DT", "FSM"]
    preconditions: list[str] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)
    test_steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    standard_ref: str = ""
    risk_level: Literal["Low", "Medium", "High"] = "Medium"
    status: Literal["Draft", "Approved", "Rejected"] = "Draft"


# FSM 状态迁移边
class FsmTransition(FlexibleModel):
    from_state: str = Field(alias="from")
    to: str
    event: str
    condition: str
    action: str


# FSM 建模完整结果
class FsmResult(FlexibleModel):
    states: list[str] = Field(default_factory=list)
    transitions: list[FsmTransition] = Field(default_factory=list)
    coverage_paths: list[str] = Field(default_factory=list)
    mermaid: str = ""


# 期望结果审查结果（Oracle 输出）
class OracleResult(FlexibleModel):
    test_id: str
    expected_result_suggestion: str
    confidence: float
    explanation: str
    needs_review: bool


# POST /generate 请求体
class GenerateRequest(FlexibleModel):
    session_id: str
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    strategies: list[Strategy] = Field(default_factory=list)
    parsed_requirements: list[ParsedRequirement] = Field(default_factory=list)
    risk_results: list[RiskResult] | None = None
    generation_mode: str = "full"


# POST /generate 响应体
class GenerateResponse(FlexibleModel):
    session_id: str
    test_cases: list[TestCase]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


# POST /fsm 请求体
class FsmRequest(FlexibleModel):
    session_id: str
    requirements: list[Requirement] | None = None
    parsed_requirements: list[ParsedRequirement] | None = None
    coverage_items: list[CoverageItem] | None = None
    state_candidates: list[str] | None = None
    requirement_ids: list[str] | None = None


# POST /fsm 响应体
class FsmResponse(FlexibleModel):
    session_id: str
    fsm: FsmResult
    test_cases: list[TestCase]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


# POST /oracle 请求体
class OracleRequest(FlexibleModel):
    session_id: str
    test_cases: list[TestCase] = Field(default_factory=list)
    test_ids: list[str] | None = None
    requirements: list[Requirement] | None = None
    source_context_ids: list[str] | None = None


# POST /oracle 响应体
class OracleResponse(FlexibleModel):
    session_id: str
    oracle_results: list[OracleResult]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)
