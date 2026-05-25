"""Step 2 routes: concept identification and risk scoring."""

from fastapi import APIRouter, Depends

from .schemas import ConceptsRequest, ConceptsResponse, RiskRequest, RiskResponse
from .service import ConceptRiskService

router = APIRouter(tags=["02 concept-risk"])


def get_concept_risk_service() -> ConceptRiskService:
    return ConceptRiskService()


@router.post("/concepts", response_model=ConceptsResponse)
async def concepts(
    req: ConceptsRequest,
    svc: ConceptRiskService = Depends(get_concept_risk_service),
) -> ConceptsResponse:
    return svc.extract_concepts(req)


@router.post("/risk", response_model=RiskResponse)
async def risk(
    req: RiskRequest,
    svc: ConceptRiskService = Depends(get_concept_risk_service),
) -> RiskResponse:
    return svc.score_risk(req)
