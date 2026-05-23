"""Repository for reading AUT requirement samples."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.app.models.common import RiskLevel, Technique
from backend.app.models.requirement import RequirementEntity

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = BACKEND_ROOT / "data" / "samples" / "aut_15_requirements.json"
FALLBACK_SAMPLE_PATH = BACKEND_ROOT.parent / "tests" / "data" / "aut_15_requirements.json"


def _safe_techniques(values: list[str] | None) -> list[Technique]:
    allowed = {"EP", "BVA", "DT", "FSM"}
    techniques = [value for value in values or ["EP"] if value in allowed]
    return techniques or ["EP"]


def _safe_priority(value: str | None) -> RiskLevel:
    if value in {"High", "Medium", "Low"}:
        return value
    return "Medium"


def _to_entity(item: dict[str, Any]) -> RequirementEntity:
    return RequirementEntity(
        requirement_id=item.get("requirement_id") or item.get("id") or "",
        raw_requirement=item.get("raw_requirement") or item.get("text") or "",
        source=item.get("source", "aut_15_requirements"),
        area=item.get("area", "general"),
        title=item.get("title", ""),
        input_fields=list(item.get("input_fields", [])),
        data_ranges=list(item.get("data_ranges", [])),
        conditions=list(item.get("conditions", [])),
        expected_action=item.get("expected_action", ""),
        techniques=_safe_techniques(item.get("techniques")),
        priority=_safe_priority(item.get("priority")),
    )


@lru_cache(maxsize=1)
def load_sample_requirements() -> list[RequirementEntity]:
    data_path = SAMPLE_PATH if SAMPLE_PATH.exists() else FALLBACK_SAMPLE_PATH
    with data_path.open(encoding="utf-8") as file:
        raw_items = json.load(file)
    return [_to_entity(item) for item in raw_items]


def get_sample_by_id(requirement_id: str) -> RequirementEntity | None:
    return next((item for item in load_sample_requirements() if item.requirement_id == requirement_id), None)


def resolve_requirements(requirement_ids: list[str] | None = None) -> list[RequirementEntity]:
    samples = load_sample_requirements()
    wanted = set(requirement_ids or [])
    if not wanted:
        return samples
    known = [item for item in samples if item.requirement_id in wanted]
    known_ids = {item.requirement_id for item in known}
    unknown = [
        RequirementEntity(
            requirement_id=requirement_id,
            raw_requirement="",
            source="runtime_request",
            title=requirement_id,
        )
        for requirement_id in requirement_ids or []
        if requirement_id not in known_ids
    ]
    return known + unknown

