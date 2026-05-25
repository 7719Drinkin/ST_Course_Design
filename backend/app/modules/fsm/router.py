"""FSM generation route (/fsm)."""

from fastapi import APIRouter, Depends

from ...core.deps import get_fsm_service
from .schemas import FsmRequest, FsmResponse
from .service import FsmService


router = APIRouter(tags=["fsm"])


@router.post("/fsm", response_model=FsmResponse)
async def fsm(
    request: FsmRequest,
    service: FsmService = Depends(get_fsm_service),
) -> FsmResponse:
    return service.generate(request)
