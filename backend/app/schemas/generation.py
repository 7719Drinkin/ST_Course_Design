"""Generation, oracle, and optimization request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.analysis import CoverageItemDto
from backend.app.models.common import OptimizeMode, RiskLevel, Technique, TestCaseStatus, Verdict


class TestCaseGenerateRequest(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)
    coverage_items: list[CoverageItemDto] = Field(default_factory=list)


class TestCaseResponse(BaseModel):
    test_id: str
    requirement_id: str
    coverage_item_id: str
    technique: Technique
    title: str
    preconditions: list[str] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)
    test_steps: list[str] = Field(default_factory=list)
    expected_result: str
    risk_level: RiskLevel
    standard_ref: str
    status: TestCaseStatus = "Draft"


class OracleRequest(BaseModel):
    test_ids: list[str] = Field(default_factory=list)


class OracleResponse(BaseModel):
    test_id: str
    llm_verdict: Verdict
    rule_verdict: Verdict
    confidence: float
    needs_review: bool


class OptimizeRequest(BaseModel):
    mode: OptimizeMode = "risk_priority"
    test_ids: list[str] = Field(default_factory=list)


class OptimizeResponse(BaseModel):
    before_count: int
    after_count: int
    mode: OptimizeMode
    reduction_rate: int
    removed_test_ids: list[str] = Field(default_factory=list)

