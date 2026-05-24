from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..tools.output_validator import validate_coverage_goals


class CoverageIdentificationAgent(BaseAgent):
    """识别业务覆盖目标，不生成测试数据或测试技术。"""

    async def run(self, context: AgentContext) -> AgentResult:
        """从 analyzed_requirements 生成 coverage_goals。"""

        try:
            if not context.analyzed_requirements:
                raise ValueError("analyzed_requirements are required.")
            if not context.risk_analysis:
                raise ValueError("risk_analysis are required.")

            result = await self._run_json_prompt(
                "coverage_identification",
                {
                    "analyzed_requirements": context.analyzed_requirements,
                    "risk_analysis": context.risk_analysis,
                },
                context,
            )
            coverage_goals = result.get("coverage_goals", [])
            validate_coverage_goals(coverage_goals)
            context.coverage_goals = coverage_goals
            return AgentResult(success=True, data={"coverage_goals": context.coverage_goals})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))
