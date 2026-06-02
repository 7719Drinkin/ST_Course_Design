from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import OracleResult
from ..tools.validation.output_validator import validate_oracle_generation


class OracleGenerationAgent(BaseAgent):
    """生成或审查 FR5 Oracle 预期结果。"""

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            if not context.oracle_test_cases:
                raise ValueError("Oracle 生成需要 test_cases。")

            payload = await self._run_json_prompt(
                "oracle_generation",
                {
                    "test_cases": context.oracle_test_cases,
                    "requirements": context.oracle_requirements,
                    "source_context_ids": context.source_context_ids,
                    "rag_context": context.rag_context or "",
                },
                context,
            )
            result = validate_oracle_generation(payload)
            self._validate_alignment(context.oracle_test_cases, result.oracle_results)
            context.oracle_results = result.oracle_results
            return AgentResult(
                success=True,
                data={"oracle_results": result.oracle_results},
            )
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    def _validate_alignment(
        self,
        test_cases: list[dict],
        oracle_results: list[OracleResult],
    ) -> None:
        input_ids = [str(item.get("test_id") or "").strip() for item in test_cases]
        output_ids = [item.test_id for item in oracle_results]

        if any(not item for item in input_ids):
            raise ValueError("所有 Oracle 输入 test_cases 都必须包含 test_id。")
        if len(input_ids) != len(output_ids):
            raise ValueError("oracle_results 必须为每条输入测试用例返回一条结果。")
        if input_ids != output_ids:
            raise ValueError("oracle_results 必须严格保持输入 test_id 顺序。")
