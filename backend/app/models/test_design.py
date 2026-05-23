"""Generated test design domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.common import OptimizeMode, RiskLevel, Technique, TestCaseStatus, Verdict


class TestCaseEntity(BaseModel):
    test_id: str
    requirement_id: str
    coverage_item_id: str
    technique: Technique
    title: str
    preconditions: list[str] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)
    test_steps: list[str] = Field(default_factory=list)
    expected_result: str
    risk_level: RiskLevel = "Medium"
    standard_ref: str
    status: TestCaseStatus = "Draft"


class FsmTransitionEntity(BaseModel):
    from_: str
    to: str
    event: str
    condition: str


class FsmResultEntity(BaseModel):
    states: list[str] = Field(default_factory=list)
    transitions: list[FsmTransitionEntity] = Field(default_factory=list)
    all_states: list[str] = Field(default_factory=list)
    all_transitions: list[str] = Field(default_factory=list)
    mermaid: str = ""


class OracleResultEntity(BaseModel):
    test_id: str
    llm_verdict: Verdict = "Pass"
    rule_verdict: Verdict = "Pass"
    confidence: float = 0.9
    needs_review: bool = False


class OptimizeResultEntity(BaseModel):
    before_count: int
    after_count: int
    mode: OptimizeMode
    reduction_rate: int
    removed_test_ids: list[str] = Field(default_factory=list)

