"""FastAPI entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Frontend-facing gateway for AutoTestDesign.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Routes will be registered here
    return app


app = create_app()
