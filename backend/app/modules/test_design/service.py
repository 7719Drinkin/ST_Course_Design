"""Step 4 business logic: test design, FSM, and oracle review."""

from __future__ import annotations

from ..store import workflow_store
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
        """Generate traceable test cases.

        TODO: 主调用 E Agent 的 EP/BVA/DT/FSM 生成器，根据 coverage_items 的
              technique 分派到对应算法。若 expected_result 或 standard_ref 缺失，
              调用 B Agent 的 Prompt 补充。
              输入：coverage_items, strategies, parsed_requirements, risk_results
              输出：list[TestCase]（含 test_id, requirement_id, coverage_item_id,
                    strategy_id, technique, preconditions, input_data, test_steps,
                    expected_result, standard_ref, risk_level, status）
        """
        workflow_store.save_many(request.session_id, "test_cases", [], "test_id")
        return GenerateResponse(
            session_id=request.session_id,
            test_cases=[],
            prompt_evidence=[],
        )

    def fsm(self, request: FsmRequest) -> FsmResponse:
        """Generate FSM state-transition model and test cases.

        TODO: 若提供了 state_candidates 则直接使用，否则调用 B Agent 从需求中
              提取候选状态语义。调用 E Agent 的 FSM 建模器生成 states、transitions、
              coverage_paths、mermaid 图描述。
              输入：requirements, parsed_requirements, coverage_items, state_candidates
              输出：FsmResult + list[TestCase]（FSM 测试用例）
        """
        workflow_store.save_object(request.session_id, "fsm", None)
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
        workflow_store.save_many(request.session_id, "oracle_results", [], "test_id")
        return OracleResponse(
            session_id=request.session_id,
            oracle_results=[],
            prompt_evidence=[],
        )
