"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path


class Config:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    REQUIREMENTS_DATA_PATH = PROJECT_ROOT / "tests" / "data" / "aut_15_requirements.json"
    JSON_AS_ASCII = False
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
