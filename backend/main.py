from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


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
    from app.modules.generation.router import router as generation_router
    from app.modules.requirements.router import router as requirements_router

    app.include_router(generation_router)
    app.include_router(requirements_router)
    return app


app = create_app()
