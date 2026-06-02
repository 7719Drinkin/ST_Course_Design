"""Step 1 routes: requirement ingest and structural parsing."""

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response

from ..store import workflow_store
from .schemas import (
    IngestRequest,
    ParseRequest,
    ParseResponse,
    PipelineStatusRequest,
    PipelineStatusResponse,
    PromptRecord,
)
from .service import IntakeParseService

router = APIRouter(tags=["01 intake-parse"])


def get_intake_parse_service() -> IntakeParseService:
    return IntakeParseService()


@router.post("/ingest", status_code=204)
async def ingest_text(
    req: IngestRequest,
    svc: IntakeParseService = Depends(get_intake_parse_service),
):
    svc.ingest_text(req.content)
    return Response(status_code=204)


@router.post("/ingest/file", status_code=204)
async def ingest_file(
    file: UploadFile,
    svc: IntakeParseService = Depends(get_intake_parse_service),
):
    raw = await file.read()
    svc.ingest_file(raw, file.filename or "upload")
    return Response(status_code=204)


@router.post("/parse", response_model=ParseResponse)
async def parse_requirements(
    req: ParseRequest,
    svc: IntakeParseService = Depends(get_intake_parse_service),
) -> ParseResponse:
    return await svc.parse(req)


@router.post("/pipeline/status", response_model=PipelineStatusResponse)
async def pipeline_status(req: PipelineStatusRequest) -> PipelineStatusResponse:
    return PipelineStatusResponse(**workflow_store.get_pipeline_status(req.session_id))
