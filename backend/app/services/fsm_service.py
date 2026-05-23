"""FSM service for the frontend Step3 card."""

from __future__ import annotations

from backend.app.models.test_design import FsmResultEntity


class FsmService:
    def build(self, requirement_ids: list[str] | None = None) -> FsmResultEntity:
        # TODO(Agent): Connect the real FSM generation module.
        return FsmResultEntity()


fsm_service = FsmService()
