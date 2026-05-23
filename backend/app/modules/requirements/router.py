"""Ingest & parse routes (/ingest, /parse)."""

from fastapi import APIRouter, Depends, UploadFile

from ...core.deps import get_requirement_service

from .schemas import IngestRequest, IngestResponse
from .service import RequirementService

router = APIRouter(tags=["requirements"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_text(
    req: IngestRequest,
    svc: RequirementService = Depends(get_requirement_service),
):
    text = svc.ingest(req.content)
    return IngestResponse(text=text, length=len(text))


@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile,
    svc: RequirementService = Depends(get_requirement_service),
):
    content = (await file.read()).decode("utf-8", errors="replace")
    text = svc.ingest(content, filename=file.filename)
    return IngestResponse(text=text, length=len(text))
