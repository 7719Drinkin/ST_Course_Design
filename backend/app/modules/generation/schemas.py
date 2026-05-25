from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, validator


ALLOWED_GENERATION_MODES = {"agent_first", "agent", "deterministic", "hybrid"}
ALLOWED_TECHNIQUES = {"EP", "BVA", "DT", "FSM"}


class GenerateRequest(BaseModel):
    requirement_id: str
    requirement_text: str
    context: dict[str, Any] = Field(default_factory=dict)
    techniques: list[str] = Field(default_factory=lambda: ["EP", "BVA", "DT"])
    use_rag: bool = True
    generation_mode: str = "agent_first"

    @validator("generation_mode")
    def validate_generation_mode(cls, value: str) -> str:
        mode = str(value).strip().lower()
        if mode not in ALLOWED_GENERATION_MODES:
            raise ValueError("generation_mode must be agent_first, agent, deterministic, or hybrid")
        return mode

    @validator("techniques", pre=True)
    def normalize_techniques(cls, value: Any) -> list[str]:
        if value is None:
            return ["EP", "BVA", "DT"]
        if isinstance(value, str):
            value = [value]

        normalized: list[str] = []
        aliases = {
            "EQUIVALENCE PARTITIONING": "EP",
            "EQUIVALENCE_PARTITIONING": "EP",
            "BOUNDARY VALUE ANALYSIS": "BVA",
            "BOUNDARY_VALUE_ANALYSIS": "BVA",
            "DECISION TABLE": "DT",
            "DECISION_TABLE": "DT",
            "FINITE STATE MACHINE": "FSM",
            "FINITE_STATE_MACHINE": "FSM",
            "STATE TRANSITION": "FSM",
            "STATE_TRANSITION": "FSM",
        }
        for item in value:
            technique = aliases.get(str(item).strip().upper(), str(item).strip().upper())
            if technique not in ALLOWED_TECHNIQUES:
                raise ValueError("techniques must contain only EP, BVA, DT, or FSM")
            if technique not in normalized:
                normalized.append(technique)
        return normalized or ["EP", "BVA", "DT"]


class GenerateMetadata(BaseModel):
    generation_mode: str
    agent_used: bool
    deterministic_used: bool
    fallback_used: bool
    fallback_reason: str | None = None
    techniques: list[str]
    case_count: int


class GenerateResponse(BaseModel):
    success: bool
    data: dict[str, Any] = Field(
        default_factory=lambda: {
            "coverage_items": [],
            "test_design_specs": [],
            "test_cases": [],
            "metadata": {},
        }
    )
    metadata: GenerateMetadata
    errors: list[str] = Field(default_factory=list)
