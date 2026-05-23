"""Interactive review routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.review import RegenerateRequest, ReviseRequest, RevisionResponse
from backend.app.services.review_service import review_service

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/history", response_model=list[RevisionResponse])
def history() -> list[RevisionResponse]:
    return [RevisionResponse(**item.model_dump()) for item in review_service.list_history()]


@router.post("/revise", response_model=RevisionResponse)
def revise(request: ReviseRequest) -> RevisionResponse:
    return RevisionResponse(**review_service.revise(request).model_dump())


@router.post("/regenerate")
def regenerate(request: RegenerateRequest) -> dict[str, object]:
    return review_service.regenerate(request)

