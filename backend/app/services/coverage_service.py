"""Coverage item service."""

from __future__ import annotations

import re

from backend.app.models.analysis import CoverageItemEntity
from backend.app.models.requirement import RequirementEntity
from backend.app.repositories.sample_repository import resolve_requirements

AREA_ALIASES = {
    "Book CRUD": "BOOK",
    "Member CRUD": "MEMBER",
    "Borrowing": "BORROW",
    "Return": "RETURN",
    "Records": "RECORDS",
    "Error Handling": "ERROR",
}


def _area_code(requirement: RequirementEntity) -> str:
    if requirement.area in AREA_ALIASES:
        return AREA_ALIASES[requirement.area]
    value = re.sub(r"[^A-Za-z0-9]+", "-", requirement.area or "GENERAL").strip("-")
    return (value or "GENERAL").upper()


def _requirement_number(requirement_id: str) -> str:
    match = re.search(r"(\d+)$", requirement_id)
    return match.group(1) if match else requirement_id.replace("REQ-", "")


class CoverageService:
    def build_items(self, requirement_ids: list[str] | None = None) -> list[CoverageItemEntity]:
        items: list[CoverageItemEntity] = []
        for requirement in resolve_requirements(requirement_ids):
            area = _area_code(requirement)
            number = _requirement_number(requirement.requirement_id)
            title = requirement.title or requirement.requirement_id
            items.append(
                CoverageItemEntity(
                    coverage_item_id=f"COV-AUT-{area}-{number}",
                    requirement_id=requirement.requirement_id,
                    description=f"Cover: {title}",
                    techniques=requirement.techniques,
                    strategy_rationale=(
                        "Selected techniques from requirement metadata; refine after RAG and Agent modules are connected."
                    ),
                )
            )
        return items


coverage_service = CoverageService()

