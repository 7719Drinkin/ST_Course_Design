"""Risk analysis service."""

from __future__ import annotations

from backend.app.models.analysis import RiskEntity


class RiskService:
    def analyze(self, requirement_ids: list[str] | None = None) -> list[RiskEntity]:
        # TODO(RAG): Connect the real risk analysis module and return requirement-level scores.
        return []


risk_service = RiskService()
