"""Step 4 routes: test design, FSM, and oracle review."""

from fastapi import APIRouter, Depends

from .schemas import (
    FsmRequest,
    FsmResponse,
    GenerateRequest,
    GenerateResponse,
    OracleRequest,
    OracleResponse,
)
from .service import TestDesignService

router = APIRouter(tags=["04 test-design"])


def get_test_design_service() -> TestDesignService:
    return TestDesignService()


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    svc: TestDesignService = Depends(get_test_design_service),
) -> GenerateResponse:
    return svc.generate(req)


@router.post("/fsm", response_model=FsmResponse)
async def fsm(
    req: FsmRequest,
    svc: TestDesignService = Depends(get_test_design_service),
) -> FsmResponse:
    return await svc.fsm(req)


@router.post("/oracle", response_model=OracleResponse)
async def oracle(
    req: OracleRequest,
    svc: TestDesignService = Depends(get_test_design_service),
) -> OracleResponse:
    return svc.oracle(req)
