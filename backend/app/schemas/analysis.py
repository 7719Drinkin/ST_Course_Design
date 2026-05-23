"""Risk and coverage request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.models.common import RiskLevel, Technique


class RequirementIdsRequest(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)


class RiskResponse(BaseModel):
    requirement_id: str
    impact: int
    likelihood: int
    score: int
    level: RiskLevel


class CoverageItemDto(BaseModel):
    coverage_item_id: str
    requirement_id: str
    description: str
    techniques: list[Technique] = Field(default_factory=list)
    strategy_rationale: str = ""
    designer_added: bool = False


class CoverageRequest(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)
    coverage_items: list[CoverageItemDto] = Field(default_factory=list)

