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
    """Base model for all agent artifacts."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def validate_non_empty_strings(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("string fields must not be empty")
        return value

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        return cls.model_validate(data)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class PromptRecord(AgentModel):
    name: str
    prompt: str
    coverage_item_id: str | None = None
    spec_id: str | None = None


class ParsedRequirement(AgentModel):
    requirement_id: str
    module: str
    raw_text: str
    description: str


class AnalyzedRequirement(AgentModel):
    requirement_id: str
    module: str
    description: str
    input_fields: list[str] = Field(default_factory=list)
    data_ranges: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    expected_action: str


class RiskAnalysisItem(AgentModel):
    requirement_id: str
    impact: ScorePart
    likelihood: ScorePart
    risk_score: StrictInt
    risk_level: RiskLevel
    test_priority: Priority
    risk_reason: str

    @model_validator(mode="after")
    def validate_risk_score(self) -> "RiskAnalysisItem":
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
    coverage_goal_id: str
    requirement_id: str
    goal: str
    related_inputs: list[str] = Field(default_factory=list)
    related_conditions: list[str] = Field(default_factory=list)
    expected_action: str


class CoverageItem(AgentModel):
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
    model_config = ConfigDict(extra="ignore", validate_assignment=True, populate_by_name=True)

    from_state: str = Field(alias="from")
    to: str
    event: str
    condition: str
    action: str


class FsmResult(AgentModel):
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
    requirements: list[ParsedRequirement] = Field(default_factory=list)
    analyzed_requirements: list[AnalyzedRequirement] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class RiskResult(AgentModel):
    risk_analysis: list[RiskAnalysisItem] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class CoverageResult(AgentModel):
    coverage_goals: list[CoverageGoal] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class StrategyResult(AgentModel):
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class GenerateResult(AgentModel):
    test_design_specs: list[TestDesignSpec] = Field(default_factory=list)
    test_cases: list[TestCaseDraft] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)


class FsmGenerationResult(AgentModel):
    fsm: FsmResult
    test_cases: list[FsmTestCaseDraft] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cases_are_non_empty(self) -> "FsmGenerationResult":
        if not self.test_cases:
            raise ValueError("test_cases 不能为空")
        return self


class OracleGenerationResult(AgentModel):
    oracle_results: list[OracleResult] = Field(default_factory=list)
    prompts_used: list[PromptRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_results_are_non_empty(self) -> "OracleGenerationResult":
        if not self.oracle_results:
            raise ValueError("oracle_results 不能为空")
        return self


class MergedTestCase(AgentModel):
    """Unified FR3/FR4 merged test-case view with source metadata."""

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
