from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..tools.output_validator import validate_risk_analysis


class RiskAnalysisAgent(BaseAgent):
    """根据需求分析结果评估测试风险和优先级。"""

    async def run(self, context: AgentContext) -> AgentResult:
        """从 analyzed_requirements 生成 risk_analysis。"""

        try:
            if not context.analyzed_requirements:
                raise ValueError("analyzed_requirements are required.")

            result = await self._run_json_prompt(
                "risk_analysis",
                {
                    "analyzed_requirements": context.analyzed_requirements,
                    "rag_context": context.rag_context or "",
                },
                context,
            )
            risk_analysis = result.get("risk_analysis", [])
            validate_risk_analysis(risk_analysis)
            context.risk_analysis = risk_analysis
            return AgentResult(success=True, data={"risk_analysis": context.risk_analysis})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))
