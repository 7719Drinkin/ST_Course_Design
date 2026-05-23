"""Ingest & parse routes (/ingest, /parse)."""

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response

from ...core.deps import get_requirement_service

from .schemas import IngestRequest
from .service import RequirementService

router = APIRouter(tags=["requirements"])


@router.post("/ingest", status_code=204)
async def ingest_text(
    req: IngestRequest,
    svc: RequirementService = Depends(get_requirement_service),
):
    svc.ingest_text(req.content)
    return Response(status_code=204)


@router.post("/ingest/file", status_code=204)
async def ingest_file(
    file: UploadFile,
    svc: RequirementService = Depends(get_requirement_service),
):
    raw = await file.read()
    svc.ingest_file(raw, file.filename or "upload")
    return Response(status_code=204)
