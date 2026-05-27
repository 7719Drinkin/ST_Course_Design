"""FastAPI dependency injection helpers."""

from ..modules.fsm.service import FsmService


def get_fsm_service() -> FsmService:
    return FsmService()
