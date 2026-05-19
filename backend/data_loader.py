"""Load shared AUT requirement sample data."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.config import Config


@lru_cache(maxsize=1)
def load_requirements(path: Path | None = None) -> list[dict[str, Any]]:
    data_path = path or Config.REQUIREMENTS_DATA_PATH
    with data_path.open(encoding="utf-8") as f:
        return json.load(f)


def get_requirement(requirement_id: str) -> dict[str, Any] | None:
    return next((req for req in load_requirements() if req["id"] == requirement_id), None)


def filter_requirements(requirement_ids: list[str] | None) -> list[dict[str, Any]]:
    reqs = load_requirements()
    if not requirement_ids:
        return reqs
    wanted = set(requirement_ids)
    return [req for req in reqs if req["id"] in wanted]
