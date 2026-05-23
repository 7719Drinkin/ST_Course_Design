"""Export request schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ExportFormat = Literal["json", "csv", "xlsx"]


class ExportRequest(BaseModel):
    format: ExportFormat = "json"
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    risk_scores: list[dict[str, Any]] = Field(default_factory=list)
    coverage_items: list[dict[str, Any]] = Field(default_factory=list)
    revisions: list[dict[str, Any]] = Field(default_factory=list)

