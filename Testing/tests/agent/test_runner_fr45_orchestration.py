from __future__ import annotations

"""End-to-end runner orchestration tests for FR3, FR4, and FR5 stages."""

import asyncio

from backend.agent.core.models import (
    AnalyzedRequirement,
    CoverageGoal,
    CoverageItem,
    CoverageResult,
    FsmGenerationResult,
    FsmResult,
    FsmTestCaseDraft,
    FsmTransitionSpec,
    GenerateResult,
    OracleGenerationResult,
    OracleResult,
    ParseResult,
    ParsedRequirement,
    RiskAnalysisItem,
    RiskResult,
    StrategyResult,
    TestCaseDraft as CaseDraftModel,
    TestDesignSpec as DesignSpecModel,
)
from backend.agent.pipeline.agent_pipeline import AgentPipeline
from backend.agent.pipeline.finalizer import finalize_pipeline_result
from backend.agent.pipeline.stages import StageName
from backend.agent.runner import _iter_pipeline_stages


def test_runner_stages_include_fr4_and_fr5_and_oracle_uses_merged_cases(monkeypatch):
    calls: dict[str, object] = {}

    parse_result = _build_parse_result()
    risk_result = _build_risk_result()
    coverage_result = _build_coverage_result()
    strategy_result = _build_strategy_result()
    generate_result = _build_generate_result()
    fsm_result = _build_fsm_result()

    async def fake_parse_requirements(self, requirement_text: str, rag_context: str | None = None):
        return parse_result

    async def fake_analyze_risk(self, analyzed_requirements, rag_context: str | None = None):
        return risk_result

    async def fake_identify_coverage(self, analyzed_requirements, risk_analysis, rag_context: str | None = None):
        return coverage_result

    async def fake_assign_strategy(
        self,
        coverage_goals,
        analyzed_requirements,
        risk_analysis,
        rag_context: str | None = None,
    ):
        return strategy_result

    async def fake_generate_tests(self, coverage_items, risk_analysis=None, rag_context: str | None = None):
        return generate_result

    async def fake_generate_fsm(
        self,
        requirements=None,
        parsed_requirements=None,
        coverage_items=None,
        state_candidates=None,
        rag_context: str | None = None,
    ):
        calls["fsm_coverage_items"] = coverage_items
        calls["fsm_requirements_size"] = len(requirements or [])
        calls["fsm_parsed_requirements_size"] = len(parsed_requirements or [])
        return fsm_result

    async def fake_generate_oracles(
        self,
        test_cases,
        requirements=None,
        source_context_ids=None,
        rag_context: str | None = None,
    ):
        calls["oracle_input_cases"] = test_cases
        return _build_oracle_result([item["test_id"] for item in test_cases])

    monkeypatch.setattr(AgentPipeline, "parse_requirements", fake_parse_requirements)
    monkeypatch.setattr(AgentPipeline, "analyze_risk", fake_analyze_risk)
    monkeypatch.setattr(AgentPipeline, "identify_coverage", fake_identify_coverage)
    monkeypatch.setattr(AgentPipeline, "assign_strategy", fake_assign_strategy)
    monkeypatch.setattr(AgentPipeline, "generate_tests", fake_generate_tests)
    monkeypatch.setattr(AgentPipeline, "generate_fsm", fake_generate_fsm)
    monkeypatch.setattr(AgentPipeline, "generate_oracles", fake_generate_oracles)

    async def collect_stages() -> list[tuple[str, object]]:
        pipeline = AgentPipeline()
        outputs: list[tuple[str, object]] = []
        async for stage, result in _iter_pipeline_stages(pipeline, "REQ TEXT", None):
            outputs.append((stage, result))
        return outputs

    stage_outputs = asyncio.run(collect_stages())
    stage_names = [item[0] for item in stage_outputs]

    assert stage_names == [
        StageName.PARSE_REQUIREMENTS,
        StageName.ANALYZE_RISK,
        StageName.IDENTIFY_COVERAGE,
        StageName.ASSIGN_STRATEGY,
        StageName.GENERATE_TESTS,
        StageName.GENERATE_FSM,
        StageName.GENERATE_ORACLE,
    ]
    assert calls["fsm_coverage_items"] is None
    assert calls["fsm_requirements_size"] == 1
    assert calls["fsm_parsed_requirements_size"] == 1

    oracle_input_cases = calls["oracle_input_cases"]
    assert isinstance(oracle_input_cases, list)
    assert [item["test_source"] for item in oracle_input_cases] == ["FR3", "FR4"]
    assert [item["technique"] for item in oracle_input_cases] == ["EP", "FSM"]


def test_finalizer_keeps_fr3_and_fr4_boundary_and_contains_fr5_results():
    parse_result = _build_parse_result()
    risk_result = _build_risk_result()
    coverage_result = _build_coverage_result()
    strategy_result = _build_strategy_result()
    generate_result = _build_generate_result()
    fsm_result = _build_fsm_result()
    oracle_result = _build_oracle_result(["TC-AUT-001-001-EP-001", "TC-AUT-FSM-001"])

    final = finalize_pipeline_result(
        parse_result,
        risk_result,
        coverage_result,
        strategy_result,
        generate_result,
        fsm_result,
        oracle_result,
    )

    assert final.fsm is not None
    assert len(final.fsm_test_cases) == 1
    assert len(final.oracle_results) == 2
    assert len(final.all_test_cases) == 2
    assert {item.source for item in final.all_test_cases} == {"FR3", "FR4"}
    assert {item.technique for item in final.coverage_items} == {"EP"}
    assert all(item.technique == "FSM" for item in final.fsm_test_cases)


def _build_parse_result() -> ParseResult:
    return ParseResult(
        requirements=[
            ParsedRequirement(
                requirement_id="REQ-AUT-001",
                module="Loans",
                raw_text="Only members with active status can borrow a book.",
                description="Borrow requires active member status.",
            )
        ],
        analyzed_requirements=[
            AnalyzedRequirement(
                requirement_id="REQ-AUT-001",
                module="Loans",
                description="Borrow requires active member status.",
                input_fields=["member_status", "book_id"],
                data_ranges=["member_status in {active, inactive}"],
                conditions=["member submits borrow request"],
                business_rules=["inactive members cannot borrow"],
                expected_action="Allow borrow only when member status is active.",
            )
        ],
        prompts_used=[],
    )


def _build_risk_result() -> RiskResult:
    return RiskResult(
        risk_analysis=[
            RiskAnalysisItem(
                requirement_id="REQ-AUT-001",
                impact=5,
                likelihood=3,
                risk_score=15,
                risk_level="High",
                test_priority="P1",
                risk_reason="Borrow permission affects core transaction.",
            )
        ],
        prompts_used=[],
    )


def _build_coverage_result() -> CoverageResult:
    return CoverageResult(
        coverage_goals=[
            CoverageGoal(
                coverage_goal_id="CG-AUT-001-001",
                requirement_id="REQ-AUT-001",
                goal="Cover active vs inactive member borrow behavior.",
                related_inputs=["member_status"],
                related_conditions=["borrow request submitted"],
                expected_action="Allow only active members to borrow.",
            )
        ],
        prompts_used=[],
    )


def _build_strategy_result() -> StrategyResult:
    return StrategyResult(
        coverage_items=[
            CoverageItem(
                coverage_item_id="COV-AUT-001-001-EP-001",
                coverage_goal_id="CG-AUT-001-001",
                requirement_id="REQ-AUT-001",
                technique="EP",
                description="Partition member status into active/inactive.",
                conditions=["borrow request submitted"],
                data_ranges=["active", "inactive"],
                input_fields=["member_status"],
                expected_action="Reject inactive member borrow attempts.",
                strategy_rationale="Status values naturally form valid/invalid partitions.",
                technique_reason="EP cleanly models status class behaviors.",
            )
        ],
        prompts_used=[],
    )


def _build_generate_result() -> GenerateResult:
    return GenerateResult(
        test_design_specs=[
            DesignSpecModel(
                spec_id="SPEC-AUT-001-001-EP-001",
                coverage_item_id="COV-AUT-001-001-EP-001",
                requirement_id="REQ-AUT-001",
                technique="EP",
                design_points=[
                    {"partition": "inactive", "expected": "reject borrow"},
                    {"partition": "active", "expected": "allow borrow"},
                ],
                standard_ref="ISO/IEC/IEEE 29119-4 EP",
            )
        ],
        test_cases=[
            CaseDraftModel(
                test_id="TC-AUT-001-001-EP-001",
                requirement_id="REQ-AUT-001",
                coverage_item_id="COV-AUT-001-001-EP-001",
                spec_id="SPEC-AUT-001-001-EP-001",
                technique="EP",
                title="Inactive member cannot borrow.",
                preconditions=["member account exists"],
                input_data={"member_status": "inactive"},
                test_steps=["Submit borrow request as inactive member."],
                expected_result="System rejects borrow request.",
                standard_ref="ISO/IEC/IEEE 29119-4 EP",
                priority="P1",
                status="Draft",
            )
        ],
        prompts_used=[],
    )


def _build_fsm_result() -> FsmGenerationResult:
    return FsmGenerationResult(
        fsm=FsmResult(
            states=["AVAILABLE", "BORROWED"],
            transitions=[
                FsmTransitionSpec(
                    **{
                        "from": "AVAILABLE",
                        "to": "BORROWED",
                        "event": "borrow",
                        "condition": "member_status == active",
                        "action": "create loan record",
                    }
                )
            ],
            coverage_paths=["AVAILABLE -> BORROWED"],
            mermaid="stateDiagram-v2\n  AVAILABLE --> BORROWED: borrow",
        ),
        test_cases=[
            FsmTestCaseDraft(
                test_id="TC-AUT-FSM-001",
                requirement_id="REQ-AUT-001",
                coverage_item_id="COV-AUT-FSM-001",
                strategy_id="STR-AUT-FSM-TRANSITION",
                technique="FSM",
                title="Active member transitions book state to BORROWED.",
                preconditions=["book is AVAILABLE", "member_status is active"],
                input_data={"event": "borrow"},
                test_steps=["Trigger borrow event for active member."],
                expected_result="State transitions from AVAILABLE to BORROWED.",
                standard_ref="ISTQB FSM",
                risk_level="Medium",
                status="Draft",
            )
        ],
        prompts_used=[],
    )


def _build_oracle_result(test_ids: list[str]) -> OracleGenerationResult:
    items = [
        OracleResult(
            test_id=test_ids[0],
            expected_result_suggestion="Borrow should be rejected for inactive member.",
            confidence=0.92,
            explanation="Requirement explicitly disallows inactive borrowing.",
            needs_review=False,
        ),
        OracleResult(
            test_id=test_ids[1],
            expected_result_suggestion="Transition to BORROWED should be verified by state check.",
            confidence=0.62,
            explanation="FSM context is partially inferred; keep manual review.",
            needs_review=True,
        ),
    ]
    return OracleGenerationResult(oracle_results=items, prompts_used=[])
