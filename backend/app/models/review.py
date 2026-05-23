"""Interactive review domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RevisionEntity(BaseModel):
    revision_id: str
    item_id: str
    item_type: str
    field_changed: str
    original_value: Any
    revised_value: Any
    revision_reason: str = ""
    timestamp: str

