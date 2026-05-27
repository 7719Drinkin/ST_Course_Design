"""Step 2 routes: risk scoring."""

from fastapi import APIRouter, Depends

from .schemas import RiskRequest, RiskResponse
from .service import ConceptRiskService

router = APIRouter(tags=["02 concept-risk"])


def get_concept_risk_service() -> ConceptRiskService:
    return ConceptRiskService()


@router.post("/risk", response_model=RiskResponse)
async def risk(
    req: RiskRequest,
    svc: ConceptRiskService = Depends(get_concept_risk_service),
) -> RiskResponse:
    return svc.score_risk(req)
