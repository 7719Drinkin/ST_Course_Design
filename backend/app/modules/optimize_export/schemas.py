"""Step 6 schemas — 测试套件优化与导出相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ..concept_risk.schemas import RiskResult
from ..coverage_strategy.schemas import CoverageItem, Strategy
from ..evidence_improve.schemas import AnalysisResult, RevisionRecord
from ..intake_parse.schemas import FlexibleModel, PromptEvidence, Requirement
from ..test_design.schemas import OracleResult, TestCase


# 测试套件优化结果
class OptimizationResult(FlexibleModel):
    objective: Literal["set_cover", "risk_priority"]
    before_count: int
    after_count: int
    kept_test_ids: list[str] = Field(default_factory=list)
    removed_test_ids: list[str] = Field(default_factory=list)
    coverage_preservation: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# 导出包（聚合所有设计阶段产出的工件）
class ExportBundle(FlexibleModel):
    requirements: list[Requirement] = Field(default_factory=list)
    risk_results: list[RiskResult] = Field(default_factory=list)
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    strategies: list[Strategy] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    fsm: dict[str, Any] | None = None
    fsm_test_cases: list[TestCase] = Field(default_factory=list)
    fsm_coverage_summary: dict[str, Any] | None = None
    oracle_results: list[OracleResult] = Field(default_factory=list)
    optimization_result: OptimizationResult | None = None
    revisions: list[RevisionRecord] = Field(default_factory=list)
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)
    analysis_results: list[AnalysisResult] = Field(default_factory=list)


# POST /optimize 请求体
class OptimizeRequest(FlexibleModel):
    session_id: str
    test_cases: list[TestCase] = Field(default_factory=list)
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    risk_results: list[RiskResult] = Field(default_factory=list)
    objective: Literal["set_cover", "risk_priority"] = "set_cover"
    preserve_high_risk_unique_coverage: bool = True


# POST /optimize 响应体
class OptimizeResponse(FlexibleModel):
    session_id: str
    optimization_result: OptimizationResult


# POST /export 请求体
class ExportRequest(FlexibleModel):
    session_id: str
    format: Literal["json", "csv", "xlsx"]
    include_revisions: bool = True
    include_prompt_evidence: bool = True
    test_case_status: Literal["all", "approved_only"] = "all"
    requirements: list[Requirement] | None = None
    risk_results: list[RiskResult] | None = None
    coverage_items: list[CoverageItem] | None = None
    strategies: list[Strategy] | None = None
    test_cases: list[TestCase] | None = None
    fsm: dict[str, Any] | None = None
    fsm_test_cases: list[TestCase] | None = None
    oracle_results: list[OracleResult] | None = None
    optimization_result: OptimizationResult | None = None
    revisions: list[RevisionRecord] | None = None
    prompt_evidence: list[PromptEvidence] | None = None
    analysis_results: list[AnalysisResult] | None = None


# POST /export 响应体（JSON 时返回 export_bundle；CSV/XLSX 时返回 file）
class ExportResponse(FlexibleModel):
    file: bytes | None = None
    export_bundle: ExportBundle | None = None
