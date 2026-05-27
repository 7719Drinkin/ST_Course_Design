"""Step 2 business logic: risk scoring."""

from __future__ import annotations

from .schemas import RiskRequest, RiskResponse


class ConceptRiskService:
    def score_risk(self, request: RiskRequest) -> RiskResponse:
        """执行 RiskAnalysisAgent 对每条 analyzed_requirement 进行风险评分。

        TODO: 接入 B Agent 的 RiskAnalysisAgent。
              输入：analyzed_requirements, rag_context
              输出：list[RiskAnalysisItem]（含 impact, likelihood, risk_score,
                    risk_level, test_priority, risk_reason）
        """
        return RiskResponse(
            risk_analysis=[],
            prompts_used=[],
        )
