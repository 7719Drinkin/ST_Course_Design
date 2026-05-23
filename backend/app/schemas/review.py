"""Interactive review request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ReviseRequest(BaseModel):
    item_id: str
    item_type: str
    field_changed: str
    original_value: Any
    revised_value: Any
    revision_reason: str = ""


class RevisionResponse(BaseModel):
    revision_id: str
    item_id: str
    item_type: str
    field_changed: str
    original_value: Any
    revised_value: Any
    revision_reason: str = ""
    timestamp: str


class RegenerateRequest(BaseModel):
    revision_id: str = ""
    item_id: str = ""
    mode: str = "incremental"

