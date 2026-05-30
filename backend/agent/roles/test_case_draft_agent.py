from __future__ import annotations

import asyncio

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import CoverageItem, RiskAnalysisItem
from ..tools.validation.output_validator import validate_test_cases


class TestCaseDraftAgent(BaseAgent):
    """把测试设计规格并行组装成人类可执行的测试用例草稿。"""

    async def run(self, context: AgentContext) -> AgentResult:

        try:
            if not context.test_design_specs:
                raise ValueError("test_design_specs are required.")

            async def _process_one(spec):
                coverage = self._find_coverage_item(
                    spec.coverage_item_id, context.coverage_items,
                )
                risk = self._find_risk_item(
                    spec.requirement_id, context.risk_analysis,
                )
                return await self._run_validated_json_prompt(
                    "test_case_draft",
                    {
                        "test_design_spec": spec,
                        "coverage_item": coverage,
                        "risk_item": risk,
                    },
                    context,
                    "test_cases",
                    validate_test_cases,
                )

            tasks = [_process_one(spec) for spec in context.test_design_specs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_cases = []
            for result in results:
                if isinstance(result, BaseException):
                    raise result
                all_cases.extend(result)

            context.test_cases = all_cases
            return AgentResult(success=True, data={"test_cases": all_cases})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    def _find_coverage_item(
        self,
        coverage_item_id: str,
        coverage_items: list[CoverageItem],
    ) -> CoverageItem | dict:
        for coverage_item in coverage_items:
            if coverage_item.coverage_item_id == coverage_item_id:
                return coverage_item
        return {}

    def _find_risk_item(
        self,
        requirement_id: str,
        risk_analysis: list[RiskAnalysisItem],
    ) -> RiskAnalysisItem | dict:
        for risk_item in risk_analysis:
            if risk_item.requirement_id == requirement_id:
                return risk_item
        return {}
