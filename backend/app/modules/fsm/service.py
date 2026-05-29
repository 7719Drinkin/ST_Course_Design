from __future__ import annotations

from typing import Any

from .schemas import FsmRequest, FsmResponse

from agent.tools.fsm import generate_fsm_tests


class FsmService:
    """Thin service wrapper around the deterministic FSM generator."""

    def generate(self, request: FsmRequest) -> FsmResponse:
        try:
            result = generate_fsm_tests(
                requirement_id=request.requirement_id,
                requirement_text=request.requirement_text,
                context=request.context,
                strategies=request.strategies,
                max_depth=request.max_depth,
            )
            return FsmResponse(
                success=bool(result.get("success", True)),
                data=result.get("data", {}) if isinstance(result.get("data"), dict) else {},
                metadata=result.get("metadata", {}) if isinstance(result.get("metadata"), dict) else {},
                errors=result.get("errors", []) if isinstance(result.get("errors"), list) else [],
            )
        except Exception as exc:
            return FsmResponse(success=False, data={}, metadata={}, errors=[str(exc)])


def generate_fsm(request: FsmRequest) -> FsmResponse:
    return FsmService().generate(request)
