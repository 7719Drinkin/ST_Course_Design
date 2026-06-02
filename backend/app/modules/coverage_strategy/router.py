"""Step 3 routes: coverage goals and strategy assignment."""

from fastapi import APIRouter, Depends

from .schemas import CoverageRequest, CoverageResponse, StrategyRequest, StrategyResponse
from .service import CoverageStrategyService

router = APIRouter(tags=["03 coverage-strategy"])


def get_coverage_strategy_service() -> CoverageStrategyService:
    return CoverageStrategyService()


@router.post("/coverage", response_model=CoverageResponse)
async def coverage(
    req: CoverageRequest,
    svc: CoverageStrategyService = Depends(get_coverage_strategy_service),
) -> CoverageResponse:
    return await svc.generate_coverage(req)


@router.post("/strategy", response_model=StrategyResponse)
async def strategy(
    req: StrategyRequest,
    svc: CoverageStrategyService = Depends(get_coverage_strategy_service),
) -> StrategyResponse:
    return await svc.assign_strategy(req)
