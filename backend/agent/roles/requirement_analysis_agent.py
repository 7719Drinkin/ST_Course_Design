from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..tools.output_validator import validate_analyzed_requirements


class RequirementAnalysisAgent(BaseAgent):
    """分析黑盒测试相关要素，不分配测试技术。"""

    async def run(self, context: AgentContext) -> AgentResult:
        """从 requirements 提取输入、范围、条件、业务规则和期望动作。"""

        try:
            if not context.requirements:
                raise ValueError("requirements are required.")

            result = await self._run_json_prompt(
                "requirement_analysis",
                {"requirements": context.requirements},
                context,
            )
            analyzed_requirements = result.get("analyzed_requirements", [])
            validate_analyzed_requirements(analyzed_requirements)
            context.analyzed_requirements = analyzed_requirements
            return AgentResult(
                success=True,
                data={"analyzed_requirements": context.analyzed_requirements},
            )
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))
