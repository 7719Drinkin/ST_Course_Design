from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ApiError(FlexibleModel):
    code: str
    message: str
    target_id: str | None = None
    detail: Any | None = None


class Requirement(FlexibleModel):
    requirement_id: str | None = None
    text: str | None = None
    raw_text: str | None = None
    description: str | None = None
    title: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedRequirement(FlexibleModel):
    requirement_id: str
    input_fields: list[str] = Field(default_factory=list)
    data_ranges: list[Any] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    expected_action: str = ""
    confidence: float = 0.0
    missing_fields: list[str] = Field(default_factory=list)


class PromptEvidence(FlexibleModel):
    evidence_id: str
    session_id: str
    prompt_name: str
    target_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    note: str = ""
    created_at: str


class Concept(FlexibleModel):
    concept_id: str
    requirement_id: str
    name: str
    type: Literal["object", "operation", "state", "constraint"]
    evidence: str


class RiskTarget(FlexibleModel):
    target_id: str
    target_type: Literal["requirement", "coverage_item"]
    text: str = ""


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


class CoverageItem(FlexibleModel):
    coverage_item_id: str
    requirement_id: str
    description: str
    technique: Literal["EP", "BVA", "DT", "FSM"]
    strategy: str = ""
    status: Literal["ai_generated", "human_revised", "human_added", "rejected"] = "ai_generated"
    source: Literal["llm", "algorithm", "designer"] = "algorithm"


class Strategy(FlexibleModel):
    strategy_id: str
    coverage_item_id: str
    technique: Literal["EP", "BVA", "DT", "FSM"]
    standard_ref: str
    reason: str
    algorithm_params: dict[str, Any] = Field(default_factory=dict)


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


class FsmTransition(FlexibleModel):
    from_state: str = Field(alias="from")
    to: str
    event: str
    condition: str
    action: str


class FsmResult(FlexibleModel):
    states: list[str] = Field(default_factory=list)
    transitions: list[FsmTransition] = Field(default_factory=list)
    coverage_paths: list[str] = Field(default_factory=list)
    mermaid: str = ""


class OracleResult(FlexibleModel):
    test_id: str
    expected_result_suggestion: str
    confidence: float
    explanation: str
    needs_review: bool


class RevisionRecord(FlexibleModel):
    revision_id: str
    session_id: str
    target_type: str
    target_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    reason: str
    created_by: str
    created_at: str


class AnalysisResult(FlexibleModel):
    requirement_id: str
    coverage_item_id: str = ""
    strategy_id: str = ""
    test_id: str = ""
    status: Literal["covered", "missing", "improved", "needs_review"]
    gap: str = ""
    improvement: str = ""


class AnalysisSummary(FlexibleModel):
    requirements_count: int
    coverage_items_count: int
    test_cases_count: int
    missing_count: int
    improved_count: int


class OptimizationResult(FlexibleModel):
    objective: Literal["set_cover", "risk_priority"]
    before_count: int
    after_count: int
    kept_test_ids: list[str] = Field(default_factory=list)
    removed_test_ids: list[str] = Field(default_factory=list)
    coverage_preservation: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExportBundle(FlexibleModel):
    requirements: list[Requirement] = Field(default_factory=list)
    risk_results: list[RiskResult] = Field(default_factory=list)
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    strategies: list[Strategy] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    optimization_result: OptimizationResult | None = None
    revisions: list[RevisionRecord] = Field(default_factory=list)
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)
    analysis_results: list[AnalysisResult] = Field(default_factory=list)


class ParseRequest(FlexibleModel):
    session_id: str
    requirement_ids: list[str] | None = None
    requirements: list[Requirement] | None = None
    include_prompt_evidence: bool = True


class ParseResponse(FlexibleModel):
    session_id: str
    parsed_requirements: list[ParsedRequirement]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)
    errors: list[ApiError] = Field(default_factory=list)


class ConceptsRequest(FlexibleModel):
    session_id: str
    requirement_ids: list[str] | None = None
    parsed_requirements: list[ParsedRequirement] | None = None
    requirements: list[Requirement] | None = None
    include_evidence: bool = True


class ConceptsResponse(FlexibleModel):
    session_id: str
    concepts: list[Concept]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


class RiskRequest(FlexibleModel):
    session_id: str
    targets: list[RiskTarget] = Field(default_factory=list)
    requirement_ids: list[str] | None = None
    risk_matrix_version: str | None = None


class RiskResponse(FlexibleModel):
    session_id: str
    risk_results: list[RiskResult]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


class CoverageRequest(FlexibleModel):
    session_id: str
    parsed_requirements: list[ParsedRequirement] | None = None
    concepts: list[Concept] | None = None
    risk_results: list[RiskResult] | None = None
    requirement_ids: list[str] | None = None


class CoverageResponse(FlexibleModel):
    session_id: str
    coverage_items: list[CoverageItem]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


class StrategyRequest(FlexibleModel):
    session_id: str
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    coverage_item_ids: list[str] | None = None
    risk_results: list[RiskResult] | None = None
    parsed_requirements: list[ParsedRequirement] | None = None


class StrategyResponse(FlexibleModel):
    session_id: str
    strategies: list[Strategy]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


class GenerateRequest(FlexibleModel):
    session_id: str
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    strategies: list[Strategy] = Field(default_factory=list)
    parsed_requirements: list[ParsedRequirement] = Field(default_factory=list)
    risk_results: list[RiskResult] | None = None
    generation_mode: str = "full"


class GenerateResponse(FlexibleModel):
    session_id: str
    test_cases: list[TestCase]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


class FsmRequest(FlexibleModel):
    session_id: str
    requirements: list[Requirement] | None = None
    parsed_requirements: list[ParsedRequirement] | None = None
    coverage_items: list[CoverageItem] | None = None
    state_candidates: list[str] | None = None
    requirement_ids: list[str] | None = None


class FsmResponse(FlexibleModel):
    session_id: str
    fsm: FsmResult
    test_cases: list[TestCase]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


class OracleRequest(FlexibleModel):
    session_id: str
    test_cases: list[TestCase] = Field(default_factory=list)
    test_ids: list[str] | None = None
    requirements: list[Requirement] | None = None
    source_context_ids: list[str] | None = None


class OracleResponse(FlexibleModel):
    session_id: str
    oracle_results: list[OracleResult]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


class RevisionsRequest(FlexibleModel):
    session_id: str
    target_type: Literal[
        "requirement",
        "parsed_requirement",
        "risk_result",
        "coverage_item",
        "strategy",
        "test_case",
    ]
    target_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    reason: str
    created_by: str


class RevisionsResponse(FlexibleModel):
    revision: RevisionRecord
    affected_ids: list[str]


class RegenerateRequest(FlexibleModel):
    session_id: str
    revision_id: str
    current_state: dict[str, Any] | None = None


class RegenerateResponse(FlexibleModel):
    session_id: str
    created: dict[str, Any] = Field(default_factory=dict)
    updated: dict[str, Any] = Field(default_factory=dict)
    unchanged: dict[str, Any] = Field(default_factory=dict)
    deprecated: dict[str, Any] = Field(default_factory=dict)
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


class AnalysisRequest(FlexibleModel):
    session_id: str
    requirements: list[Requirement] | None = None
    coverage_items: list[CoverageItem] | None = None
    strategies: list[Strategy] | None = None
    test_cases: list[TestCase] | None = None
    revisions: list[RevisionRecord] | None = None


class AnalysisResponse(FlexibleModel):
    session_id: str
    analysis_results: list[AnalysisResult]
    summary: AnalysisSummary


class OptimizeRequest(FlexibleModel):
    session_id: str
    test_cases: list[TestCase] = Field(default_factory=list)
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    risk_results: list[RiskResult] = Field(default_factory=list)
    objective: Literal["set_cover", "risk_priority"] = "set_cover"
    preserve_high_risk_unique_coverage: bool = True


class OptimizeResponse(FlexibleModel):
    session_id: str
    optimization_result: OptimizationResult


class ExportRequest(FlexibleModel):
    session_id: str
    format: Literal["json", "csv", "xlsx"]
    include_revisions: bool = True
    include_prompt_evidence: bool = True
    test_case_status: Literal["all", "approved_only"] = "all"


class ExportResponse(FlexibleModel):
    file: bytes | None = None
    export_bundle: ExportBundle | None = None
