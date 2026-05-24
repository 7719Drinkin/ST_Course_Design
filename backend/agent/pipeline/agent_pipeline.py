from __future__ import annotations

from typing import Any

from ..core.agent_context import AgentContext
from ..core.base_agent import BaseAgent
from ..prompts.prompt_builder import PromptBuilder
from ..roles.coverage_identification_agent import CoverageIdentificationAgent
from ..roles.requirement_analysis_agent import RequirementAnalysisAgent
from ..roles.requirement_parse_agent import RequirementParseAgent
from ..roles.technique_assignment_agent import TechniqueAssignmentAgent
from ..roles.test_case_draft_agent import TestCaseDraftAgent
from ..roles.test_design_spec_agent import TestDesignSpecAgent
from ..tools.id_normalizer import normalize_all_ids
from ..tools.llm_client import LLMClient
from ..tools.rag_client import RAGClient
from ..tools.traceability_checker import check_traceability
from .pipeline_state import PipelineState


class AgentPipeline:
    """黑盒测试设计的内部编排器。

    该类保留给 runner 和测试使用；对外推荐使用 generate_blackbox_tests。
    执行顺序固定为 6 个 Agent，并在设计规格生成前按需获取 RAG 上下文。
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
        rag_client: RAGClient | None = None,
    ) -> None:
        """创建共享工具实例，并按黑盒测试设计流程组装 Agent 列表。"""

        shared_llm_client = llm_client or LLMClient()
        shared_prompt_builder = prompt_builder or PromptBuilder()
        self.rag_client = rag_client or RAGClient()
        self.steps: list[tuple[str, BaseAgent]] = [
            ("requirement_parse", RequirementParseAgent(shared_llm_client, shared_prompt_builder)),
            ("requirement_analysis", RequirementAnalysisAgent(shared_llm_client, shared_prompt_builder)),
            ("coverage_identification", CoverageIdentificationAgent(shared_llm_client, shared_prompt_builder)),
            ("technique_assignment", TechniqueAssignmentAgent(shared_llm_client, shared_prompt_builder)),
            ("test_design_spec", TestDesignSpecAgent(shared_llm_client, shared_prompt_builder)),
            ("test_case_draft", TestCaseDraftAgent(shared_llm_client, shared_prompt_builder)),
        ]

    async def run(self, requirement_text: str, rag_context: str | None = None) -> dict[str, Any]:
        """运行完整 Agent 链路，返回 pipeline 内部结果结构。

        如果调用方传入 rag_context，会直接使用该上下文；否则在进入
        TestDesignSpecAgent 前通过 RAGClient 自动检索。任何步骤失败都会
        停止后续执行，并返回 partial_result 方便调试。
        """

        context = AgentContext(requirement_text=requirement_text, rag_context=rag_context)
        state = PipelineState(context=context)

        for step_name, agent in self.steps:
            state.current_step = step_name
            if step_name == "test_design_spec" and not context.rag_context:
                rag_result = await self._retrieve_rag_context(context, state)
                if rag_result is not None:
                    return rag_result

            result = await agent.run(context)
            if not result.success:
                state.errors.append({"step": step_name, "error": result.error})
                return {
                    "success": False,
                    "failed_step": step_name,
                    "error": result.error,
                    "partial_result": self._build_result(context),
                }

        try:
            normalize_all_ids(context)
            check_traceability(context)
        except Exception as exc:
            state.errors.append({"step": "post_process", "error": str(exc)})
            return {
                "success": False,
                "failed_step": "post_process",
                "error": str(exc),
                "partial_result": self._build_result(context),
            }

        return {"success": True, **self._build_result(context)}

    async def _retrieve_rag_context(
        self,
        context: AgentContext,
        state: PipelineState,
    ) -> dict[str, Any] | None:
        """为测试设计规格阶段获取标准/技术上下文。

        RAG 调用集中在 pipeline，不散落到各个 Agent，便于后续替换
        RAG 实现，也便于失败时统一返回 rag_retrieval 错误。
        """

        state.current_step = "rag_retrieval"
        try:
            query = self._build_rag_query(context)
            context.rag_context = await self.rag_client.retrieve(query)
            return None
        except Exception as exc:
            state.errors.append({"step": "rag_retrieval", "error": str(exc)})
            return {
                "success": False,
                "failed_step": "rag_retrieval",
                "error": str(exc),
                "partial_result": self._build_result(context),
            }

    def _build_rag_query(self, context: AgentContext) -> str:
        """根据已分配的 coverage_items 构造面向标准知识库的检索 query。"""

        base_terms = [
            "black-box testing",
            "equivalence partitioning",
            "boundary value analysis",
            "decision table testing",
            "ISO/IEC/IEEE 29119-4",
            "ISTQB",
        ]
        techniques = sorted(
            {
                str(item.get("technique", "")).strip()
                for item in context.coverage_items
                if isinstance(item, dict) and item.get("technique")
            }
        )
        item_parts: list[str] = []
        for item in context.coverage_items:
            if not isinstance(item, dict):
                continue
            item_parts.extend(
                [
                    str(item.get("description", "")),
                    " ".join(str(value) for value in item.get("conditions", []) or []),
                    " ".join(str(value) for value in item.get("data_ranges", []) or []),
                ]
            )

        return "\n".join(
            [
                " ".join(base_terms),
                f"Assigned techniques: {', '.join(techniques)}",
                "Coverage item context:",
                "\n".join(part for part in item_parts if part.strip()),
            ]
        )

    def _build_result(self, context: AgentContext) -> dict[str, Any]:
        """从共享上下文提取 pipeline 的标准内部输出字段。"""

        return {
            "requirements": context.requirements,
            "analyzed_requirements": context.analyzed_requirements,
            "coverage_goals": context.coverage_goals,
            "coverage_items": context.coverage_items,
            "test_design_specs": context.test_design_specs,
            "test_cases": context.test_cases,
            "prompts_used": context.prompts_used,
        }
