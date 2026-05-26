from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import CoverageItem, RiskAnalysisItem
from ..tools.validation.output_validator import validate_test_cases


class TestCaseDraftAgent(BaseAgent):
    """把测试设计规格组装成人类可执行的测试用例草稿。"""

    async def run(self, context: AgentContext) -> AgentResult:
        """为每个 test_design_spec 单独生成 test_cases 并汇总。"""

        try:
            if not context.test_design_specs:
                raise ValueError("test_design_specs are required.")

            all_cases = []
            for test_design_spec in context.test_design_specs:
                coverage_item = self._find_coverage_item(
                    test_design_spec.coverage_item_id,
                    context.coverage_items,
                )
                risk_item = self._find_risk_item(
                    test_design_spec.requirement_id,
                    context.risk_analysis,
                )
                test_cases = await self._run_validated_json_prompt(
                    "test_case_draft",
                    {
                        "test_design_spec": test_design_spec,
                        "coverage_item": coverage_item,
                        "risk_item": risk_item,
                    },
                    context,
                    "test_cases",
                    validate_test_cases,
                )
                all_cases.extend(test_cases)

            # 所有 spec 都生成成功后再写回，保证 context.test_cases 是完整批次结果。
            context.test_cases = all_cases
            return AgentResult(success=True, data={"test_cases": all_cases})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    def _find_coverage_item(
        self,
        coverage_item_id: str,
        coverage_items: list[CoverageItem],
    ) -> CoverageItem | dict:
        """按 coverage_item_id 找到当前 spec 对应的 coverage_item。"""

        for coverage_item in coverage_items:
            if coverage_item.coverage_item_id == coverage_item_id:
                return coverage_item
        return {}

    def _find_risk_item(
        self,
        requirement_id: str,
        risk_analysis: list[RiskAnalysisItem],
    ) -> RiskAnalysisItem | dict:
        """根据 requirement_id 查找当前测试设计规格对应的风险优先级。"""

        for risk_item in risk_analysis:
            if risk_item.requirement_id == requirement_id:
                return risk_item
        return {}
