from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..tools.validation.output_validator import validate_requirements


class RequirementParseAgent(BaseAgent):
    """把原始需求文本拆成原子需求，不做条件/技术分析。"""

    async def run(self, context: AgentContext) -> AgentResult:
        """执行需求拆分，并把 requirements 写入共享上下文。"""

        try:
            if not context.requirement_text or not context.requirement_text.strip():
                raise ValueError("requirement_text is required.")

            requirements = await self._run_validated_json_prompt(
                "requirement_parse",
                {"requirement_text": context.requirement_text},
                context,
                "requirements",
                validate_requirements,
            )
            # 阶段结果写回 AgentContext，后续 role 只读取强类型 ParsedRequirement。
            context.requirements = requirements
            return AgentResult(success=True, data={"requirements": context.requirements})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))
