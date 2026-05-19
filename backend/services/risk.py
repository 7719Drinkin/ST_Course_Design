"""Risk and coverage derivation service."""

from __future__ import annotations

from typing import Any

from backend.data_loader import filter_requirements
from backend.services.traceability import coverage_id_for_requirement


def priority_to_risk(priority: str) -> tuple[int, int, str]:
    mapping = {
        "High": (5, 5, "High"),
        "Medium": (3, 3, "Medium"),
        "Low": (2, 2, "Low"),
    }
    return mapping.get(priority, (3, 3, "Medium"))


def build_risk_entries(requirement_ids: list[str] | None = None) -> list[dict[str, Any]]:
    entries = []
    for req in filter_requirements(requirement_ids):
        impact, likelihood, level = priority_to_risk(req.get("priority", "Medium"))
        entries.append(
            {
                "requirement_id": req["id"],
                "impact": impact,
                "likelihood": likelihood,
                "score": impact * likelihood,
                "level": level,
            }
        )
    return entries


def build_coverage_items(requirement_ids: list[str] | None = None) -> list[dict[str, Any]]:
    return [
        {
            "coverage_item_id": coverage_id_for_requirement(req),
            "requirement_id": req["id"],
            "description": f"Cover: {req['title']}",
            "techniques": req.get("techniques", ["EP"]),
            "strategy_rationale": "Derived from requirement techniques; replaceable by RAG-based strategy selection.",
        }
        for req in filter_requirements(requirement_ids)
    ]
