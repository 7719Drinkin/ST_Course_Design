"""Requirement domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.models.common import RiskLevel, Technique


class RequirementEntity(BaseModel):
    requirement_id: str
    raw_requirement: str
    source: str = "manual_input"
    area: str = "general"
    title: str = ""
    input_fields: list[str] = Field(default_factory=list)
    data_ranges: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    expected_action: str = ""
    techniques: list[Technique] = Field(default_factory=lambda: ["EP"])
    priority: RiskLevel = "Medium"

