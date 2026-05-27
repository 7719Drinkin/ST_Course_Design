"""Step 5 schemas — 人工修订、差量再生成、结果分析相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ..coverage_strategy.schemas import CoverageItem, Strategy
from ..intake_parse.schemas import FlexibleModel, PromptEvidence, Requirement
from ..test_design.schemas import TestCase


# 修订记录（设计者人工修改的审计轨迹）
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


# 单条分析结果（REQ → COV → TC 的可追溯性状态）
class AnalysisResult(FlexibleModel):
    requirement_id: str
    coverage_item_id: str = ""
    strategy_id: str = ""
    test_id: str = ""
    status: Literal["covered", "missing", "improved", "needs_review"]
    gap: str = ""
    improvement: str = ""


# 分析汇总统计
class AnalysisSummary(FlexibleModel):
    requirements_count: int
    coverage_items_count: int
    test_cases_count: int
    missing_count: int
    improved_count: int


# POST /revisions 请求体
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


# POST /revisions 响应体
class RevisionsResponse(FlexibleModel):
    revision: RevisionRecord
    affected_ids: list[str]


# POST /regenerate 请求体
class RegenerateRequest(FlexibleModel):
    session_id: str
    revision_id: str
    current_state: dict[str, Any] | None = None


# POST /regenerate 响应体
class RegenerateResponse(FlexibleModel):
    session_id: str
    created: dict[str, Any] = Field(default_factory=dict)
    updated: dict[str, Any] = Field(default_factory=dict)
    unchanged: dict[str, Any] = Field(default_factory=dict)
    deprecated: dict[str, Any] = Field(default_factory=dict)
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)


# POST /analysis 请求体
class AnalysisRequest(FlexibleModel):
    session_id: str
    requirements: list[Requirement] | None = None
    coverage_items: list[CoverageItem] | None = None
    strategies: list[Strategy] | None = None
    test_cases: list[TestCase] | None = None
    revisions: list[RevisionRecord] | None = None


# POST /analysis 响应体
class AnalysisResponse(FlexibleModel):
    session_id: str
    analysis_results: list[AnalysisResult]
    summary: AnalysisSummary
