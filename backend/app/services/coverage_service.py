"""Coverage item service."""

from __future__ import annotations

from backend.app.models.analysis import CoverageItemEntity


class CoverageService:
    def build_items(self, requirement_ids: list[str] | None = None) -> list[CoverageItemEntity]:
        # TODO(Agent): Connect the real coverage identification module.
        return []


coverage_service = CoverageService()
