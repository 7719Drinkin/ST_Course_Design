"""Generation, FSM, Oracle, and optimization routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.fsm import FsmCoverageResponse, FsmRequest, FsmResponse, FsmTransitionResponse
from backend.app.schemas.generation import (
    OptimizeRequest,
    OptimizeResponse,
    OracleRequest,
    OracleResponse,
    TestCaseGenerateRequest,
    TestCaseResponse,
)
from backend.app.services.fsm_service import fsm_service
from backend.app.services.generation_service import generation_service
from backend.app.services.optimization_service import optimization_service
from backend.app.services.oracle_service import oracle_service

router = APIRouter(tags=["generation"])


@router.post("/generate", response_model=list[TestCaseResponse])
def generate(request: TestCaseGenerateRequest) -> list[TestCaseResponse]:
    cases = generation_service.generate(request.requirement_ids, request.coverage_items)
    return [TestCaseResponse(**item.model_dump()) for item in cases]


@router.post("/fsm", response_model=FsmResponse)
def fsm(request: FsmRequest) -> FsmResponse:
    result = fsm_service.build(request.requirement_ids)
    return FsmResponse(
        states=result.states,
        transitions=[
            FsmTransitionResponse(from_=item.from_, to=item.to, event=item.event, condition=item.condition)
            for item in result.transitions
        ],
        coverage=FsmCoverageResponse(all_states=result.all_states, all_transitions=result.all_transitions),
        mermaid=result.mermaid,
    )


@router.post("/oracle", response_model=list[OracleResponse])
def oracle(request: OracleRequest) -> list[OracleResponse]:
    return [OracleResponse(**item.model_dump()) for item in oracle_service.evaluate(request.test_ids)]


@router.post("/optimize", response_model=OptimizeResponse)
def optimize(request: OptimizeRequest) -> OptimizeResponse:
    result = optimization_service.optimize(request.mode, request.test_ids)
    return OptimizeResponse(**result.model_dump())

