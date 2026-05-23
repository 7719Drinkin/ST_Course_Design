"""API router registry for FastAPI bootstrap."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes.analysis import router as analysis_router
from backend.app.api.routes.dashboard import router as dashboard_router
from backend.app.api.routes.exports import router as export_router
from backend.app.api.routes.generation import router as generation_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.requirements import router as requirement_router
from backend.app.api.routes.reviews import router as review_router

api_routers: list[APIRouter] = [
    health_router,
    dashboard_router,
    requirement_router,
    analysis_router,
    generation_router,
    export_router,
    review_router,
]

