"""Dashboard routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.dashboard import DashboardResponse
from backend.app.services.dashboard_service import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard() -> DashboardResponse:
    return dashboard_service.get_dashboard()

