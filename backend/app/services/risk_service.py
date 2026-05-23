"""Risk analysis service."""

from __future__ import annotations

from backend.app.models.analysis import RiskEntity
from backend.app.models.common import RiskLevel
from backend.app.repositories.sample_repository import resolve_requirements


def _priority_to_risk(priority: RiskLevel) -> tuple[int, int, RiskLevel]:
    mapping: dict[RiskLevel, tuple[int, int, RiskLevel]] = {
        "High": (5, 5, "High"),
        "Medium": (3, 3, "Medium"),
        "Low": (2, 2, "Low"),
    }
    return mapping.get(priority, (3, 3, "Medium"))


class RiskService:
    def analyze(self, requirement_ids: list[str] | None = None) -> list[RiskEntity]:
        results: list[RiskEntity] = []
        for requirement in resolve_requirements(requirement_ids):
            impact, likelihood, level = _priority_to_risk(requirement.priority)
            results.append(
                RiskEntity(
                    requirement_id=requirement.requirement_id,
                    impact=impact,
                    likelihood=likelihood,
                    score=impact * likelihood,
                    level=level,
                )
            )
        return results


risk_service = RiskService()

