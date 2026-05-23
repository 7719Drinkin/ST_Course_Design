"""Dashboard summary service."""

from __future__ import annotations

from backend.app.schemas.dashboard import DashboardResponse, DashboardSummaryResponse, RagasSummaryResponse
from backend.app.services.generation_service import generation_service
from backend.app.services.risk_service import risk_service
from backend.app.repositories.sample_repository import load_sample_requirements


class DashboardService:
    def get_dashboard(self) -> DashboardResponse:
        samples = load_sample_requirements()
        risks = risk_service.analyze([item.requirement_id for item in samples])
        generated_cases = generation_service.generate([item.requirement_id for item in samples])
        return DashboardResponse(
            summary=DashboardSummaryResponse(
                total_requirements=len(samples),
                generated_tests=len(generated_cases),
                high_risk_count=sum(1 for risk in risks if risk.level == "High"),
                ci_status="passing",
            ),
            ragas=RagasSummaryResponse(enabled=False),
        )


dashboard_service = DashboardService()

