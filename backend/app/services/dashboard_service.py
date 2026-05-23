"""Dashboard summary service."""

from __future__ import annotations

from backend.app.schemas.dashboard import DashboardResponse, DashboardSummaryResponse, RagasSummaryResponse


class DashboardService:
    def get_dashboard(self) -> DashboardResponse:
        return DashboardResponse(
            summary=DashboardSummaryResponse(
                total_requirements=0,
                generated_tests=0,
                high_risk_count=0,
                ci_status="idle",
            ),
            ragas=RagasSummaryResponse(enabled=False),
        )


dashboard_service = DashboardService()
