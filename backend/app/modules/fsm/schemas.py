from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, validator


class FsmRequest(BaseModel):
    requirement_id: str
    requirement_text: str
    context: dict[str, Any] = Field(default_factory=dict)
    strategies: list[str] | None = None
    max_depth: int = 6

    @validator("strategies", pre=True)
    def normalize_strategies(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = [value]
        allowed = {"ALL_STATES", "ALL_TRANSITIONS"}
        normalized: list[str] = []
        for item in value:
            strategy = str(item).strip().upper()
            if strategy not in allowed:
                raise ValueError("strategies must contain only ALL_STATES or ALL_TRANSITIONS")
            if strategy not in normalized:
                normalized.append(strategy)
        return normalized

    @validator("max_depth")
    def validate_max_depth(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_depth must be at least 1")
        return value


class FsmResponse(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
