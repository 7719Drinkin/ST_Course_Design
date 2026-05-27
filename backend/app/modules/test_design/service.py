"""Step 4 business logic: test design, FSM, and oracle review."""

from __future__ import annotations

from .schemas import (
    FsmRequest,
    FsmResponse,
    FsmResult,
    GenerateRequest,
    GenerateResponse,
    OracleRequest,
    OracleResponse,
)


class TestDesignService:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """执行 TestDesignSpecAgent 和 TestCaseDraftAgent，生成测试设计规格和用例。

        TODO: 接入 B Agent 的 TestDesignSpecAgent 和 TestCaseDraftAgent。
              输入：coverage_items, risk_analysis, rag_context
              输出：list[TestDesignSpec] + list[TestCaseDraft]
        """
        return GenerateResponse(
            test_design_specs=[],
            test_cases=[],
            prompts_used=[],
        )

    def fsm(self, request: FsmRequest) -> FsmResponse:
        """Generate FSM state-transition model and test cases.

        TODO: 若提供了 state_candidates 则直接使用，否则调用 B Agent 从需求中
              提取候选状态语义。调用 E Agent 的 FSM 建模器生成 states、transitions、
              coverage_paths、mermaid 图描述。
              输入：requirements, parsed_requirements, coverage_items, state_candidates
              输出：FsmResult + list[TestCase]（FSM 测试用例）
        """
        return FsmResponse(
            session_id=request.session_id,
            fsm=FsmResult(states=[], transitions=[], coverage_paths=[], mermaid=""),
            test_cases=[],
            prompt_evidence=[],
        )

    def oracle(self, request: OracleRequest) -> OracleResponse:
        """Review or generate expected_result for test cases.

        TODO: 接入 B Agent 的 Oracle Prompt，结合 RAG 上下文审查 expected_result。
              输入：test_cases, requirements, source_context_ids（RAG）
              输出：list[OracleResult]（含 test_id, expected_result_suggestion,
                    confidence, explanation, needs_review）
              低置信度（confidence < 0.7）时标记 needs_review=True。
        """
        return OracleResponse(
            session_id=request.session_id,
            oracle_results=[],
            prompt_evidence=[],
        )
