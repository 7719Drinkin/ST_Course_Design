"""Dashboard response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_requirements: int
    generated_tests: int
    high_risk_count: int
    ci_status: str


class RagasSummaryResponse(BaseModel):
    enabled: bool
    answer_relevancy: float | None = None
    faithfulness: float | None = None


class DashboardResponse(BaseModel):
    summary: DashboardSummaryResponse
    ragas: RagasSummaryResponse

