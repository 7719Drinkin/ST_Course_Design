"""Global settings loaded once from .env files."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_ROOT / ".env", override=False)


def _read_csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AutoTestDesign Backend")
    app_version: str = os.getenv("APP_VERSION", "0.4.0")
    environment: str = os.getenv("APP_ENV", "local")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: _read_csv_env(
            "CORS_ORIGINS",
            ("http://localhost:5173", "http://127.0.0.1:5173"),
        )
    )
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    agent_base_url: str = os.getenv("AGENT_BASE_URL", "")
    rag_enabled: bool = os.getenv("RAG_ENABLED", "false").lower() in {"1", "true", "yes"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

