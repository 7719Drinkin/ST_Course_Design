"""Requirement ingest and parse request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    source_type: str = "text"
    content: Any = ""


class RequirementResponse(BaseModel):
    requirement_id: str
    raw_requirement: str
    source: str


class IngestResponse(BaseModel):
    requirements: list[RequirementResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ParseRequest(BaseModel):
    requirement_id: str
    raw_requirement: str = ""
    text: str = ""


class ParseResponse(BaseModel):
    requirement_id: str
    input_fields: list[str] = Field(default_factory=list)
    data_ranges: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    expected_action: str = ""
    confidence: float = 0.0
    missing_fields: list[str] = Field(default_factory=list)
    source_context_ids: list[str] = Field(default_factory=list)
    prompt_template_id: str = ""
    retrieved_context_ids: list[str] = Field(default_factory=list)
    model_name: str = ""
    output_schema_version: str = "parse-v1"

