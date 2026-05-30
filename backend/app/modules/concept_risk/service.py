"""Step 2 business logic: risk scoring — store-first read, no inline pipeline."""

from __future__ import annotations

from ..store import workflow_store
from .schemas import RiskRequest, RiskResponse


class ConceptRiskService:
    async def score_risk(self, request: RiskRequest) -> RiskResponse:
        stored = workflow_store.get_list(request.session_id, "risk_analysis")
        if stored:
            return RiskResponse(risk_analysis=stored, prompts_used=[])
        return RiskResponse(risk_analysis=[], prompts_used=[])
