from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import (
    AnalyzedRequirement,
    CoverageGoal,
    CoverageItem,
    CoverageResult,
    FsmGenerationResult,
    GenerateResult,
    ParseResult,
    RiskAnalysisItem,
    RiskResult,
    StrategyResult,
)
from ..prompts.prompt_builder import PromptBuilder
from ..roles.coverage_identification_agent import CoverageIdentificationAgent
from ..roles.fsm_modeling_agent import FsmModelingAgent
from ..roles.requirement_analysis_agent import RequirementAnalysisAgent
from ..roles.requirement_parse_agent import RequirementParseAgent
from ..roles.risk_analysis_agent import RiskAnalysisAgent
from ..roles.technique_assignment_agent import TechniqueAssignmentAgent
from ..roles.test_case_draft_agent import TestCaseDraftAgent
from ..roles.test_design_spec_agent import TestDesignSpecAgent
from ..tools.clients.llm_client import LLMClient
from ..tools.clients.rag_client import RAGClient
from ..tools.validation.output_validator import validate_model_list
from .errors import StageExecutionError
from .stages import StageName


class AgentPipeline:
    """阶段执行器：只负责创建上下文、调用 role agent、返回阶段结果。"""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
        rag_client: RAGClient | None = None,
    ) -> None:
        """初始化共享依赖，保证同一次 pipeline 调用复用同一套 LLM/Prompt/RAG。"""

        shared_llm_client = llm_client or LLMClient()
        shared_prompt_builder = prompt_builder or PromptBuilder()
        self.rag_client = rag_client or RAGClient()
        self.requirement_parse_agent = RequirementParseAgent(
            shared_llm_client,
            shared_prompt_builder,
        )
        self.requirement_analysis_agent = RequirementAnalysisAgent(
            shared_llm_client,
            shared_prompt_builder,
        )
        self.risk_analysis_agent = RiskAnalysisAgent(
            shared_llm_client,
            shared_prompt_builder,
        )
        self.coverage_identification_agent = CoverageIdentificationAgent(
            shared_llm_client,
            shared_prompt_builder,
        )
        self.technique_assignment_agent = TechniqueAssignmentAgent(
            shared_llm_client,
            shared_prompt_builder,
        )
        self.test_design_spec_agent = TestDesignSpecAgent(
            shared_llm_client,
            shared_prompt_builder,
        )
        self.test_case_draft_agent = TestCaseDraftAgent(
            shared_llm_client,
            shared_prompt_builder,
        )
        self.fsm_modeling_agent = FsmModelingAgent(
            shared_llm_client,
            shared_prompt_builder,
        )

    async def parse_requirements(
        self,
        requirement_text: str,
        rag_context: str | None = None,
    ) -> ParseResult:
        """需求解析阶段：拆分原始需求，并补齐测试设计所需的需求语义。"""

        context = AgentContext(requirement_text=requirement_text, rag_context=rag_context)
        # 一个对外阶段包含两个内部 role；失败时统一归到 parse_requirements。
        await self._run_agent(
            StageName.PARSE_REQUIREMENTS,
            self.requirement_parse_agent,
            context,
        )
        await self._run_agent(
            StageName.PARSE_REQUIREMENTS,
            self.requirement_analysis_agent,
            context,
        )
        return ParseResult(
            requirements=context.requirements,
            analyzed_requirements=context.analyzed_requirements,
            prompts_used=list(context.prompts_used),
        )

    async def analyze_risk(
        self,
        analyzed_requirements: Sequence[AnalyzedRequirement],
        rag_context: str | None = None,
    ) -> RiskResult:
        """风险分析阶段：基于已分析需求生成风险分数和测试优先级。"""

        context = AgentContext(
            analyzed_requirements=_model_list(analyzed_requirements, AnalyzedRequirement),
            rag_context=rag_context,
        )
        await self._run_agent(StageName.ANALYZE_RISK, self.risk_analysis_agent, context)
        return RiskResult(
            risk_analysis=context.risk_analysis,
            prompts_used=list(context.prompts_used),
        )

    async def identify_coverage(
        self,
        analyzed_requirements: Sequence[AnalyzedRequirement],
        risk_analysis: Sequence[RiskAnalysisItem],
        rag_context: str | None = None,
    ) -> CoverageResult:
        """覆盖识别阶段：只识别覆盖目标，不提前分配 EP/BVA/DT。"""

        context = AgentContext(
            analyzed_requirements=_model_list(analyzed_requirements, AnalyzedRequirement),
            risk_analysis=_model_list(risk_analysis, RiskAnalysisItem),
            rag_context=rag_context,
        )
        await self._run_agent(
            StageName.IDENTIFY_COVERAGE,
            self.coverage_identification_agent,
            context,
        )
        return CoverageResult(
            coverage_goals=context.coverage_goals,
            prompts_used=list(context.prompts_used),
        )

    async def assign_strategy(
        self,
        coverage_goals: Sequence[CoverageGoal],
        analyzed_requirements: Sequence[AnalyzedRequirement],
        risk_analysis: Sequence[RiskAnalysisItem],
        rag_context: str | None = None,
    ) -> StrategyResult:
        """策略分配阶段：为覆盖目标生成覆盖项和技术选择理由。"""

        context = AgentContext(
            coverage_goals=_model_list(coverage_goals, CoverageGoal),
            analyzed_requirements=_model_list(analyzed_requirements, AnalyzedRequirement),
            risk_analysis=_model_list(risk_analysis, RiskAnalysisItem),
            rag_context=rag_context,
        )
        await self._run_agent(
            StageName.ASSIGN_STRATEGY,
            self.technique_assignment_agent,
            context,
        )
        return StrategyResult(
            coverage_items=context.coverage_items,
            prompts_used=list(context.prompts_used),
        )

    async def generate_tests(
        self,
        coverage_items: Sequence[CoverageItem],
        risk_analysis: Sequence[RiskAnalysisItem] | None = None,
        rag_context: str | None = None,
    ) -> GenerateResult:
        """测试生成阶段：生成设计规格和 Draft 测试用例。"""

        context = AgentContext(
            coverage_items=_model_list(coverage_items, CoverageItem),
            risk_analysis=_model_list(risk_analysis or [], RiskAnalysisItem),
            rag_context=rag_context,
        )
        if not context.rag_context:
            # RAG 只服务测试设计阶段；失败时归属 generate_tests，便于前端定位。
            await self._retrieve_rag_context(context)
        await self._run_agent(StageName.GENERATE_TESTS, self.test_design_spec_agent, context)
        await self._run_agent(StageName.GENERATE_TESTS, self.test_case_draft_agent, context)
        return GenerateResult(
            test_design_specs=context.test_design_specs,
            test_cases=context.test_cases,
            prompts_used=list(context.prompts_used),
        )

    async def generate_fsm(
        self,
        requirements: Sequence[Any] | None = None,
        parsed_requirements: Sequence[Any] | None = None,
        coverage_items: Sequence[Any] | None = None,
        state_candidates: Sequence[str] | None = None,
        rag_context: str | None = None,
    ) -> FsmGenerationResult:
        """FR4 FSM modeling stage: prompt-based FSM model and FSM cases."""

        context = AgentContext(
            fsm_requirements=_dict_list(requirements or []),
            fsm_parsed_requirements=_dict_list(parsed_requirements or []),
            fsm_coverage_items=_dict_list(coverage_items or []),
            state_candidates=[str(item) for item in (state_candidates or [])],
            rag_context=rag_context,
        )
        await self._run_agent(StageName.GENERATE_FSM, self.fsm_modeling_agent, context)
        if context.fsm is None:
            raise StageExecutionError(StageName.GENERATE_FSM, "FSM prompt did not return fsm.", context)
        return FsmGenerationResult(
            fsm=context.fsm,
            test_cases=context.fsm_test_cases,
            prompts_used=list(context.prompts_used),
        )

    async def _run_agent(
        self,
        stage: str,
        agent: BaseAgent,
        context: AgentContext,
    ) -> AgentResult:
        """执行内部 role agent，并把失败统一包装成阶段异常交给 runner 处理。"""

        result = await agent.run(context)
        if not result.success:
            raise StageExecutionError(stage, str(result.error or "Agent stage failed."), context)
        return result

    async def _retrieve_rag_context(self, context: AgentContext) -> None:
        """按覆盖项信息检索标准依据，结果写回当前阶段上下文。"""

        try:
            query = self._build_rag_query(context)
            context.rag_context = await self.rag_client.retrieve(query)
        except Exception as exc:
            raise StageExecutionError(StageName.GENERATE_TESTS, str(exc), context) from exc

    def _build_rag_query(self, context: AgentContext) -> str:
        """把覆盖项、技术和标准关键词整理成 RAG 查询文本。"""

        base_terms = [
            "black-box testing",
            "equivalence partitioning",
            "boundary value analysis",
            "decision table testing",
            "ISO/IEC/IEEE 29119-4",
            "ISTQB",
        ]
        techniques = sorted({item.technique for item in context.coverage_items if item.technique})
        item_parts: list[str] = []
        for item in context.coverage_items:
            item_parts.extend(
                [
                    item.description,
                    " ".join(item.conditions),
                    " ".join(item.data_ranges),
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


async def parse_requirements(
    requirement_text: str,
    rag_context: str | None = None,
) -> ParseResult:
    """模块级便捷入口：执行需求解析阶段。"""

    return await AgentPipeline().parse_requirements(requirement_text, rag_context)


async def analyze_risk(
    analyzed_requirements: Sequence[AnalyzedRequirement],
    rag_context: str | None = None,
) -> RiskResult:
    """模块级便捷入口：执行风险分析阶段。"""

    return await AgentPipeline().analyze_risk(analyzed_requirements, rag_context)


async def identify_coverage(
    analyzed_requirements: Sequence[AnalyzedRequirement],
    risk_analysis: Sequence[RiskAnalysisItem],
    rag_context: str | None = None,
) -> CoverageResult:
    """模块级便捷入口：执行覆盖识别阶段。"""

    return await AgentPipeline().identify_coverage(analyzed_requirements, risk_analysis, rag_context)


async def assign_strategy(
    coverage_goals: Sequence[CoverageGoal],
    analyzed_requirements: Sequence[AnalyzedRequirement],
    risk_analysis: Sequence[RiskAnalysisItem],
    rag_context: str | None = None,
) -> StrategyResult:
    """模块级便捷入口：执行策略分配阶段。"""

    return await AgentPipeline().assign_strategy(
        coverage_goals,
        analyzed_requirements,
        risk_analysis,
        rag_context,
    )


async def generate_tests(
    coverage_items: Sequence[CoverageItem],
    risk_analysis: Sequence[RiskAnalysisItem] | None = None,
    rag_context: str | None = None,
) -> GenerateResult:
    """模块级便捷入口：执行测试生成阶段。"""

    return await AgentPipeline().generate_tests(coverage_items, risk_analysis, rag_context)


async def generate_fsm(
    requirements: Sequence[Any] | None = None,
    parsed_requirements: Sequence[Any] | None = None,
    coverage_items: Sequence[Any] | None = None,
    state_candidates: Sequence[str] | None = None,
    rag_context: str | None = None,
) -> FsmGenerationResult:
    """Module-level convenience entry for the FR4 FSM modeling stage."""

    return await AgentPipeline().generate_fsm(
        requirements,
        parsed_requirements,
        coverage_items,
        state_candidates,
        rag_context,
    )


def _model_list(items: Sequence[Any], model: type[Any]) -> list[Any]:
    """阶段入口兼容 dict/model，进入 AgentContext 前统一转成强类型模型。"""

    return validate_model_list(list(items), model, model.__name__)


def _dict_list(items: Sequence[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump(mode="json", by_alias=True))
        elif isinstance(item, dict):
            result.append(dict(item))
        elif hasattr(item, "to_dict"):
            result.append(item.to_dict())
        else:
            raise ValueError(f"FSM input item must be dict/model-like, got {type(item)!r}")
    return result
