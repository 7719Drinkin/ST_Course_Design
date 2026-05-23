"""Test case generation service."""

from __future__ import annotations

from backend.app.models.test_design import TestCaseEntity
from backend.app.schemas.analysis import CoverageItemDto


class GenerationService:
    def generate(
        self,
        requirement_ids: list[str] | None = None,
        coverage_items: list[CoverageItemDto] | None = None,
    ) -> list[TestCaseEntity]:
        # TODO(Agent): Connect the real test generation module.
        return []


generation_service = GenerationService()
