"""Step 4 schemas — 测试用例生成、FSM 状态迁移、Oracle 审查相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from ..concept_risk.schemas import RiskAnalysisItem
from ..coverage_strategy.schemas import CoverageItem
from ..intake_parse.schemas import FlexibleModel, ParsedRequirement, PromptEvidence, PromptRecord, Requirement


# 测试用例（FSM / Oracle 等辅助端点使用）
class TestCase(FlexibleModel):
    test_id: str
    requirement_id: str
    coverage_item_id: str
    strategy_id: str = ""
    technique: Literal["EP", "BVA", "DT", "FSM"]
    title: str = ""
    preconditions: list[str] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)
    test_steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    standard_ref: str = ""
    risk_level: Literal["Low", "Medium", "High"] = "Medium"
    status: Literal["Draft", "Approved", "Rejected"] = "Draft"


# TestDesignSpecAgent 产物：测试设计规格
class TestDesignSpec(FlexibleModel):
    spec_id: str                   # SPEC-AUT-*
    coverage_item_id: str          # 来源覆盖项
    requirement_id: str            # 来源需求
    technique: Literal["EP", "BVA", "DT"]
    design_points: list[object] = Field(default_factory=list)
    standard_ref: str = ""


# TestCaseDraftAgent 产物：可追踪测试用例草案
class TestCaseDraft(FlexibleModel):
    test_id: str                   # TC-AUT-*
    requirement_id: str            # 来源需求
    coverage_item_id: str          # 来源覆盖项
    spec_id: str                   # 来源测试设计规格
    technique: Literal["EP", "BVA", "DT"]
    title: str = ""
    preconditions: list[str] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)
    test_steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    standard_ref: str = ""
    priority: Literal["P1", "P2", "P3"] = "P2"
    status: Literal["Draft"] = "Draft"


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
    coverage: dict[str, list[str]] = Field(
        default_factory=lambda: {"all_states": [], "all_transitions": []}
    )
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
    session_id: str = "SESSION-CURRENT"
    requirement_text: str = ""
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    risk_analysis: list[RiskAnalysisItem] | None = None
    rag_context: str | None = None


# POST /generate 响应体
class GenerateResponse(FlexibleModel):
    test_design_specs: list[TestDesignSpec]
    test_cases: list[TestCaseDraft]
    prompts_used: list[PromptRecord] = Field(default_factory=list)


# POST /fsm 请求体
class FsmRequest(FlexibleModel):
    session_id: str = "default"
    requirement_ids: list[str] = Field(default_factory=list)
    requirement_id: str | None = None
    requirement_text: str | None = None
    requirements: list[Requirement] | None = None
    parsed_requirements: list[ParsedRequirement] | None = None
    coverage_items: list[CoverageItem] | None = None
    state_candidates: list[str] | None = None
    strategies: list[str] | None = None
    rag_context: str | None = None
    max_depth: int = 6

    @field_validator("strategies", mode="before")
    @classmethod
    def normalize_strategies(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = [value]
        allowed = {"ALL_STATES", "ALL_TRANSITIONS"}
        normalized: list[str] = []
        for item in value:
            strategy = str(item).strip().upper()
            if strategy not in allowed:
                raise ValueError("strategies 只能包含 ALL_STATES 或 ALL_TRANSITIONS")
            if strategy not in normalized:
                normalized.append(strategy)
        return normalized

    @field_validator("max_depth")
    @classmethod
    def validate_max_depth(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_depth 至少为 1")
        return value


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
    requirements: list[Requirement] | None = None
    source_context_ids: list[str] | None = None
    requirement_text: str = ""
    rag_context: str | None = None


# POST /oracle 响应体
class OracleResponse(FlexibleModel):
    session_id: str
    oracle_results: list[OracleResult]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)
