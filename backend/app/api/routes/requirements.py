"""Requirement ingest and parse routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.requirements import IngestRequest, IngestResponse, ParseRequest, ParseResponse
from backend.app.services.requirement_service import requirement_service

router = APIRouter(tags=["requirements"])


@router.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    requirements, errors = requirement_service.ingest(request.source_type, request.content)
    return IngestResponse(requirements=requirements, errors=errors)


@router.post("/parse", response_model=ParseResponse)
def parse(request: ParseRequest) -> ParseResponse:
    raw_requirement = request.raw_requirement or request.text
    return requirement_service.parse(request.requirement_id, raw_requirement)

