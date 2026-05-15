"""Load AUT requirement sample data for reference API implementation."""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "tests" / "data" / "aut_15_requirements.json"


def load_requirements() -> list[dict]:
    with DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_by_id(requirement_id: str) -> dict | None:
    for req in load_requirements():
        if req["id"] == requirement_id:
            return req
    return None
