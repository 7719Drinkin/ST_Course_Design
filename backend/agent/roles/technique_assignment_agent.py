from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..tools.output_validator import validate_coverage_items


class TechniqueAssignmentAgent(BaseAgent):
    """为覆盖目标分配 EP/BVA/DT 三类黑盒技术。"""

    async def run(self, context: AgentContext) -> AgentResult:
        """结合 coverage_goals 和 analyzed_requirements 生成 coverage_items。"""

        try:
            if not context.coverage_goals:
                raise ValueError("coverage_goals are required.")
            if not context.analyzed_requirements:
                raise ValueError("analyzed_requirements are required.")
            if not context.risk_analysis:
                raise ValueError("risk_analysis are required.")

            result = await self._run_json_prompt(
                "technique_assignment",
                {
                    "coverage_goals": context.coverage_goals,
                    "analyzed_requirements": context.analyzed_requirements,
                    "risk_analysis": context.risk_analysis,
                },
                context,
            )
            coverage_items = result.get("coverage_items", [])
            validate_coverage_items(coverage_items)
            context.coverage_items = coverage_items
            return AgentResult(success=True, data={"coverage_items": context.coverage_items})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))
