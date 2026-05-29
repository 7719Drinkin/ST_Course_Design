from __future__ import annotations

from typing import Annotated, Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Technique = Literal["EP", "BVA", "DT"]
FsmTechnique = Literal["FSM"]
RiskLevel = Literal["High", "Medium", "Low"]
Priority = Literal["P1", "P2", "P3"]
ScorePart = Annotated[int, Field(ge=1, le=5, strict=True)]
StrictInt = Annotated[int, Field(strict=True)]
Confidence = Annotated[float, Field(ge=0, le=1)]

T = TypeVar("T", bound="AgentModel")


class AgentModel(BaseModel):
    """Agent 层通用基类模型，统一输入容错与序列化行为。"""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def validate_non_empty_strings(cls, value: Any) -> Any:
        """所有字符串字段都不允许纯空白。"""
        if isinstance(value, str) and not value.strip():
            raise ValueError("string fields must not be empty")
        return value

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """从 dict 恢复为强类型模型。"""
        return cls.model_validate(data)

    def to_dict(self) -> dict[str, Any]:
        """转回普通 dict，供外层兼容处理。"""
        return self.model_dump()


class PromptRecord(AgentModel):
    """记录一次 Prompt 调用证据。"""

    name: str
    prompt: str
    coverage_item_id: str | None = None
    spec_id: str | None = None


class ParsedRequirement(AgentModel):
    """需求解析结果。"""

    requirement_id: str
    module: str
    raw_text: str
    description: str


class AnalyzedRequirement(AgentModel):
    """需求语义分析结果。"""

    requirement_id: str
    module: str
    description: str
    input_fields: list[str] = Field(default_factory=list)
    data_ranges: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    expected_action: str


class RiskAnalysisItem(AgentModel):
    """风险分析结果。"""

    requirement_id: str
    impact: ScorePart
    likelihood: ScorePart
    risk_score: StrictInt
    risk_level: RiskLevel
    test_priority: Priority
    risk_reason: str

    @model_validator(mode="after")
    def validate_risk_score(self) -> "RiskAnalysisItem":
        """校验风险分数、风险等级、优先级一致性。"""
        if self.risk_score != self.impact * self.likelihood:
            raise ValueError("risk_score must equal impact * likelihood")
        expected_level: RiskLevel = (
            "High" if self.risk_score >= 15 else "Medium" if self.risk_score >= 8 else "Low"
        )
        expected_priority: Priority = {"High": "P1", "Medium": "P2", "Low": "P3"}[expected_level]
        if self.risk_level != expected_level:
            raise ValueError("risk_level does not match risk_score")
        if self.test_priority != expected_priority:
            raise ValueError("test_priority does not match risk_level")
        return self


class CoverageGoal(AgentModel):
    """覆盖目标（未分配技术）。"""

    coverage_goal_id: str
    requirement_id: str
    goal: str
    related_inputs: list[str] = Field(default_factory=list)
    related_conditions: list[str] = Field(default_factory=list)
    expected_action: str


class CoverageItem(AgentModel):
    """覆盖项（已分配 EP/BVA/DT 技术）。"""

    coverage_item_id: str
    coverage_goal_id: str
    requirement_id: str
    technique: Technique
    description: str
    conditions: list[str] = Field(default_factory=list)
    data_ranges: list[str] = Field(default_factory=list)
    input_fields: list[str] = Field(default_factory=list)
    expected_action: str
    strategy_rationale: str
    technique_reason: str

    @model_validator(mode="after")
    def validate_reason(self) -> "CoverageItem":
        if not self.technique_reason.strip():
            raise ValueError("technique_reason must not be empty")
        return self


class TestDesignSpec(AgentModel):
    """测试设计规格。"""

    spec_id: str
    coverage_item_id: str
    requirement_id: str
    technique: Technique
    design_points: list[dict[str, Any]] = Field(default_factory=list)
    standard_ref: str

    @model_validator(mode="after")
    def validate_design_points(self) -> "TestDesignSpec":
        if not self.design_points:
            raise ValueError("design_points must not be empty")
        return self


class TestCaseDraft(AgentModel):
    """FR3 产出的测试用例草稿。"""

    test_id: str
    requirement_id: str
    coverage_item_id: str
    spec_id: str
    technique: Technique
    title: str
    preconditions: list[str] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)
    test_steps: list[str] = Field(default_factory=list)
    expected_result: str
    standard_ref: str
    priority: Priority
    status: Literal["Draft"]

    @model_validator(mode="after")
    def validate_expected_result(self) -> "TestCaseDraft":
        if not self.expected_result.strip():
            raise ValueError("expected_result must not be empty")
        return self


class FsmTransitionSpec(AgentModel):
    """FR4 FSM 迁移边。"""

    model_config = ConfigDict(extra="ignore", validate_assignment=True, populate_by_name=True)

    from_state: str = Field(alias="from")
    to: str
    event: str
    condition: str
    action: str


class FsmResult(AgentModel):
    """FR4 FSM 建模结果。"""

    states: list[str] = Field(default_factory=list)
    transitions: list[FsmTransitionSpec] = Field(default_factory=list)
    coverage_paths: list[str] = Field(default_factory=list)
    mermaid: str

    @model_validator(mode="after")
    def validate_fsm_is_non_empty(self) -> "FsmResult":
        if not self.states:
            raise ValueError("fsm.states 不能为空")
        if not self.transitions:
            raise ValueError("fsm.transitions 不能为空")
        if not self.coverage_paths:
            raise ValueError("fsm.coverage_paths 不能为空")
        return self


class FsmTestCaseDraft(AgentModel):
    """FR4 产出的 FSM 测试用例草稿。"""

    test_id: str
    requirement_id: str
    coverage_item_id: str
    strategy_id: str = ""
    technique: FsmTechnique
    title: str
    preconditions: list[str] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)
    test_steps: list[str] = Field(default_factory=list)
    expected_result: str
    standard_ref: str
    risk_level: RiskLevel = "Medium"
    status: Literal["Draft"] = "Draft"

    @model_validator(mode="after")
    def validate_fsm_case(self) -> "FsmTestCaseDraft":
        if self.technique != "FSM":
            raise ValueError("FSM test case technique must be FSM")
        if not self.expected_result.strip():
            raise ValueError("expected_result 不能为空")
        return self


class OracleResult(AgentModel):
    """FR5 Oracle 结果。"""

    test_id: str
    expected_result_suggestion: str
    confidence: Confidence
    explanation: str
    needs_review: bool

    @model_validator(mode="after")
    def validate_review_flag(self) -> "OracleResult":
        if self.confidence < 0.7 and not self.needs_review:
            raise ValueError("confidence < 0.7 时 needs_review 必须为 true")
        return self


class ParseResult(AgentModel):
    """FR1 解析阶段输出。"""

    requirements: list[ParsedRequirement] = Field(default_factory=list)
    analyzed_requirements: list[AnalyzedRequirement] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class RiskResult(AgentModel):
    """FR2 风险分析阶段输出。"""

    risk_analysis: list[RiskAnalysisItem] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class CoverageResult(AgentModel):
    """FR3 覆盖目标识别阶段输出。"""

    coverage_goals: list[CoverageGoal] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class StrategyResult(AgentModel):
    """FR3 技术分配阶段输出。"""

    coverage_items: list[CoverageItem] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class GenerateResult(AgentModel):
    """FR3 用例生成阶段输出。"""

    test_design_specs: list[TestDesignSpec] = Field(default_factory=list)
    test_cases: list[TestCaseDraft] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class FsmGenerationResult(AgentModel):
    """FR4 FSM 阶段输出。"""

    fsm: FsmResult
    test_cases: list[FsmTestCaseDraft] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cases_are_non_empty(self) -> "FsmGenerationResult":
        if not self.test_cases:
            raise ValueError("test_cases 不能为空")
        return self


class OracleGenerationResult(AgentModel):
    """FR5 Oracle 阶段输出。"""

    oracle_results: list[OracleResult] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_results_are_non_empty(self) -> "OracleGenerationResult":
        if not self.oracle_results:
            raise ValueError("oracle_results 不能为空")
        return self


class MergedTestCase(AgentModel):
    """FR3/FR4 合并后的统一测试用例视图（含来源标记）。"""

    source: Literal["FR3", "FR4"]
    test_id: str
    requirement_id: str
    technique: str
    test_case: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_merged_case(self) -> "MergedTestCase":
        if not self.test_case:
            raise ValueError("test_case 不能为空")
        return self


class FullPipelineResult(AgentModel):
    """主流程最终汇总结果（FR1-FR5）。"""

    requirements: list[ParsedRequirement] = Field(default_factory=list)
    analyzed_requirements: list[AnalyzedRequirement] = Field(default_factory=list)
    risk_analysis: list[RiskAnalysisItem] = Field(default_factory=list)
    coverage_goals: list[CoverageGoal] = Field(default_factory=list)
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    test_design_specs: list[TestDesignSpec] = Field(default_factory=list)
    test_cases: list[TestCaseDraft] = Field(default_factory=list)
    fsm: FsmResult | None = None
    fsm_test_cases: list[FsmTestCaseDraft] = Field(default_factory=list)
    all_test_cases: list[MergedTestCase] = Field(default_factory=list)
    oracle_results: list[OracleResult] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)
