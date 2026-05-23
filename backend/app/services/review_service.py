"""Interactive review service."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.schemas.review import RegenerateRequest, ReviseRequest
from backend.app.models.review import RevisionEntity

_REVISION_HISTORY: list[RevisionEntity] = []


class ReviewService:
    def list_history(self) -> list[RevisionEntity]:
        return list(_REVISION_HISTORY)

    def revise(self, request: ReviseRequest) -> RevisionEntity:
        record = RevisionEntity(
            revision_id=f"REV-{len(_REVISION_HISTORY) + 1:04d}",
            item_id=request.item_id,
            item_type=request.item_type,
            field_changed=request.field_changed,
            original_value=request.original_value,
            revised_value=request.revised_value,
            revision_reason=request.revision_reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        _REVISION_HISTORY.append(record)
        return record

    def regenerate(self, request: RegenerateRequest) -> dict[str, object]:
        # TODO(Agent): Use revision diff to trigger incremental regeneration.
        return {
            "revision_id": request.revision_id,
            "item_id": request.item_id,
            "mode": request.mode,
            "status": "pending_generation",
            "generated_test_cases": [],
        }


review_service = ReviewService()

