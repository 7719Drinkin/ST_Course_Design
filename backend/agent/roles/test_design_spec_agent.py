from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import RiskAnalysisItem
from ..tools.validation.output_validator import validate_test_design_specs


class TestDesignSpecAgent(BaseAgent):
    """按 coverage_item 逐项展开测试设计规格。"""

    async def run(self, context: AgentContext) -> AgentResult:
        """为每个 coverage_item 单独生成 test_design_specs 并汇总。"""

        try:
            if not context.coverage_items:
                raise ValueError("coverage_items are required.")

            all_specs = []
            for coverage_item in context.coverage_items:
                risk_item = self._find_risk_item(
                    coverage_item.requirement_id,
                    context.risk_analysis,
                )
                test_design_specs = await self._run_validated_json_prompt(
                    "test_design_spec",
                    {
                        "coverage_item": coverage_item,
                        "rag_context": context.rag_context or "",
                        "risk_item": risk_item,
                    },
                    context,
                    "test_design_specs",
                    validate_test_design_specs,
                )
                all_specs.extend(test_design_specs)

            # 批量生成完成后再写回上下文，避免中途失败留下半成品给下游阶段。
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
        """根据 requirement_id 查找当前需求对应的风险分析结果。"""

        for risk_item in risk_analysis:
            if risk_item.requirement_id == requirement_id:
                return risk_item
        return {}
