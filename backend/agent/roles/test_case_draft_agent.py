from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..tools.output_validator import validate_test_cases


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
                    str(test_design_spec.get("coverage_item_id", "")),
                    context.coverage_items,
                )
                result = await self._run_json_prompt(
                    "test_case_draft",
                    {
                        "test_design_spec": test_design_spec,
                        "coverage_item": coverage_item,
                    },
                    context,
                )
                test_cases = result.get("test_cases", [])
                validate_test_cases(test_cases)
                all_cases.extend(test_cases)

            context.test_cases = all_cases
            return AgentResult(success=True, data={"test_cases": all_cases})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    def _find_coverage_item(
        self,
        coverage_item_id: str,
        coverage_items: list,
    ) -> dict:
        """按 coverage_item_id 找到当前 spec 对应的 coverage_item。"""

        for coverage_item in coverage_items:
            if (
                isinstance(coverage_item, dict)
                and coverage_item.get("coverage_item_id") == coverage_item_id
            ):
                return coverage_item
        return {}
