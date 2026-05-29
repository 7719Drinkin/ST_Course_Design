"""Step 5 routes: evidence review and improvement."""

from fastapi import APIRouter, Depends

from .schemas import (
    AnalysisRequest,
    AnalysisResponse,
    RegenerateRequest,
    RegenerateResponse,
    RevisionsRequest,
    RevisionsResponse,
)
from .service import EvidenceImproveService

router = APIRouter(tags=["05 evidence-improve"])


def get_evidence_improve_service() -> EvidenceImproveService:
    return EvidenceImproveService()


@router.post("/revisions", response_model=RevisionsResponse)
async def revisions(
    req: RevisionsRequest,
    svc: EvidenceImproveService = Depends(get_evidence_improve_service),
) -> RevisionsResponse:
    return svc.save_revision(req)


@router.post("/regenerate", response_model=RegenerateResponse)
async def regenerate(
    req: RegenerateRequest,
    svc: EvidenceImproveService = Depends(get_evidence_improve_service),
) -> RegenerateResponse:
    return await svc.regenerate(req)


@router.post("/analysis", response_model=AnalysisResponse)
async def analysis(
    req: AnalysisRequest,
    svc: EvidenceImproveService = Depends(get_evidence_improve_service),
) -> AnalysisResponse:
    return svc.analyze(req)
