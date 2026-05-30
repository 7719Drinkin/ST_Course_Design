from __future__ import annotations

import asyncio

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import RiskAnalysisItem
from ..tools.validation.output_validator import validate_test_design_specs


class TestDesignSpecAgent(BaseAgent):
    """按 coverage_item 并行展开测试设计规格。"""

    async def run(self, context: AgentContext) -> AgentResult:

        try:
            if not context.coverage_items:
                raise ValueError("coverage_items are required.")

            async def _process_one(item):
                risk = self._find_risk_item(
                    item.requirement_id, context.risk_analysis,
                )
                return await self._run_validated_json_prompt(
                    "test_design_spec",
                    {
                        "coverage_item": item,
                        "rag_context": context.rag_context or "",
                        "risk_item": risk,
                    },
                    context,
                    "test_design_specs",
                    validate_test_design_specs,
                )

            tasks = [_process_one(item) for item in context.coverage_items]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_specs = []
            for result in results:
                if isinstance(result, BaseException):
                    raise result
                all_specs.extend(result)

            context.test_design_specs = all_specs
            return AgentResult(
                success=True,
                data={"test_design_specs": all_specs},
            )
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    def _find_risk_item(
        self,
        requirement_id: str,
        risk_analysis: list[RiskAnalysisItem],
    ) -> RiskAnalysisItem | dict:
        for risk_item in risk_analysis:
            if risk_item.requirement_id == requirement_id:
                return risk_item
        return {}
