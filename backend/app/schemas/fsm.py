"""FSM request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FsmRequest(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)


class FsmTransitionResponse(BaseModel):
    from_: str = Field(alias="from")
    to: str
    event: str
    condition: str

    model_config = ConfigDict(populate_by_name=True)


class FsmCoverageResponse(BaseModel):
    all_states: list[str] = Field(default_factory=list)
    all_transitions: list[str] = Field(default_factory=list)


class FsmResponse(BaseModel):
    states: list[str] = Field(default_factory=list)
    transitions: list[FsmTransitionResponse] = Field(default_factory=list)
    coverage: FsmCoverageResponse = Field(default_factory=FsmCoverageResponse)
    mermaid: str = ""
