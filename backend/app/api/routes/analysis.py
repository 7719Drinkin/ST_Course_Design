"""Risk and coverage routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.analysis import CoverageItemDto, CoverageRequest, RequirementIdsRequest, RiskResponse
from backend.app.services.coverage_service import coverage_service
from backend.app.services.risk_service import risk_service

router = APIRouter(tags=["analysis"])


@router.post("/risk", response_model=list[RiskResponse])
def risk(request: RequirementIdsRequest) -> list[RiskResponse]:
    return [RiskResponse(**item.model_dump()) for item in risk_service.analyze(request.requirement_ids)]


@router.post("/coverage", response_model=list[CoverageItemDto])
def coverage(request: CoverageRequest) -> list[CoverageItemDto]:
    return [CoverageItemDto(**item.model_dump()) for item in coverage_service.build_items(request.requirement_ids)]

