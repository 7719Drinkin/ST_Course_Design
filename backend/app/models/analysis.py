"""Risk and coverage domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.models.common import RiskLevel, Technique


class RiskEntity(BaseModel):
    requirement_id: str
    impact: int
    likelihood: int
    score: int
    level: RiskLevel


class CoverageItemEntity(BaseModel):
    coverage_item_id: str
    requirement_id: str
    description: str
    techniques: list[Technique] = Field(default_factory=lambda: ["EP"])
    strategy_rationale: str = ""
    designer_added: bool = False

