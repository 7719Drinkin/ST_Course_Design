from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.agent import runner
from backend.agent.core.models import (
    CoverageResult,
    GenerateResult,
    ParseResult,
    RiskResult,
    StrategyResult,
)
from backend.agent.pipeline.errors import StageExecutionError
from backend.agent.pipeline.finalizer import build_full_pipeline_result
from backend.agent.pipeline.stages import StageName
from backend.agent.tools.validation.output_validator import (
    validate_analyzed_requirements,
    validate_coverage_goals,
    validate_coverage_items,
    validate_requirements,
    validate_risk_analysis,
    validate_test_cases,
    validate_test_design_specs,
)
from tests.test_agent_validation import _valid_result


def test_generate_blackbox_tests_runs_stages_in_order(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(runner, "AgentPipeline", _fake_pipeline_factory(calls))

    def fake_finalize(
        parse_result: ParseResult,
        risk_result: RiskResult,
        coverage_result: CoverageResult,
        strategy_result: StrategyResult,
        generate_result: GenerateResult,
    ):
        calls.append(StageName.FINAL_VALIDATION)
        return build_full_pipeline_result(
            parse_result,
            risk_result,
            coverage_result,
            strategy_result,
            generate_result,
        )

    monkeypatch.setattr(runner, "finalize_pipeline_result", fake_finalize)

    result = asyncio.run(runner.generate_blackbox_tests("有效需求", rag_context="标准上下文"))

    assert result["success"] is True
    assert calls == [
        StageName.PARSE_REQUIREMENTS,
        StageName.ANALYZE_RISK,
        StageName.IDENTIFY_COVERAGE,
        StageName.ASSIGN_STRATEGY,
        StageName.GENERATE_TESTS,
        StageName.FINAL_VALIDATION,
    ]


def test_generate_blackbox_tests_rejects_empty_input():
    result = asyncio.run(runner.generate_blackbox_tests("  "))

    assert result["success"] is False
    assert result["failed_step"] == StageName.INPUT_VALIDATION


def test_generate_blackbox_tests_preserves_stage_execution_error(monkeypatch):
    class FailingPipeline(_fake_pipeline_factory([])):
        async def analyze_risk(self, analyzed_requirements, rag_context=None):
            raise StageExecutionError(StageName.ANALYZE_RISK, "risk failed")

    monkeypatch.setattr(runner, "AgentPipeline", FailingPipeline)

    result = asyncio.run(runner.generate_blackbox_tests("有效需求"))

    assert result["success"] is False
    assert result["failed_step"] == StageName.ANALYZE_RISK
    assert result["error"] == "risk failed"


def test_generate_blackbox_tests_unknown_error_maps_to_agent_runner(monkeypatch):
    class BrokenPipeline(_fake_pipeline_factory([])):
        async def parse_requirements(self, requirement_text, rag_context=None):
            raise RuntimeError("unexpected")

    monkeypatch.setattr(runner, "AgentPipeline", BrokenPipeline)

    result = asyncio.run(runner.generate_blackbox_tests("有效需求"))

    assert result["success"] is False
    assert result["failed_step"] == StageName.AGENT_RUNNER


def test_stream_emits_each_stage_once_and_final_after_final_validation(monkeypatch):
    monkeypatch.setattr(runner, "AgentPipeline", _fake_pipeline_factory([]))

    events = asyncio.run(_collect_stream_events("有效需求"))

    stage_events = [data["stage"] for event, data in events if event == "stage"]
    assert stage_events == [
        StageName.PARSE_REQUIREMENTS,
        StageName.ANALYZE_RISK,
        StageName.IDENTIFY_COVERAGE,
        StageName.ASSIGN_STRATEGY,
        StageName.GENERATE_TESTS,
        StageName.FINAL_VALIDATION,
    ]
    assert events[-1][0] == "final"


def test_stream_reports_final_validation_failure(monkeypatch):
    monkeypatch.setattr(runner, "AgentPipeline", _fake_pipeline_factory([]))

    def fail_finalization(*_args: Any):
        raise StageExecutionError(StageName.FINAL_VALIDATION, "final gate failed")

    monkeypatch.setattr(runner, "finalize_pipeline_result", fail_finalization)

    events = asyncio.run(_collect_stream_events("有效需求"))

    assert events[-1][0] == "stage_error"
    assert events[-1][1]["stage"] == StageName.FINAL_VALIDATION
    assert all(event != "final" for event, _data in events)


def _fake_pipeline_factory(calls: list[str]):
    parse_result, risk_result, coverage_result, strategy_result, generate_result = _stage_results()

    class FakePipeline:
        async def parse_requirements(self, requirement_text, rag_context=None):
            calls.append(StageName.PARSE_REQUIREMENTS)
            return parse_result

        async def analyze_risk(self, analyzed_requirements, rag_context=None):
            calls.append(StageName.ANALYZE_RISK)
            return risk_result

        async def identify_coverage(self, analyzed_requirements, risk_analysis, rag_context=None):
            calls.append(StageName.IDENTIFY_COVERAGE)
            return coverage_result

        async def assign_strategy(
            self,
            coverage_goals,
            analyzed_requirements,
            risk_analysis,
            rag_context=None,
        ):
            calls.append(StageName.ASSIGN_STRATEGY)
            return strategy_result

        async def generate_tests(self, coverage_items, risk_analysis=None, rag_context=None):
            calls.append(StageName.GENERATE_TESTS)
            return generate_result

    return FakePipeline


def _stage_results():
    data = _valid_result()
    parse_result = ParseResult(
        requirements=validate_requirements(data["requirements"]),
        analyzed_requirements=validate_analyzed_requirements(data["analyzed_requirements"]),
    )
    risk_result = RiskResult(risk_analysis=validate_risk_analysis(data["risk_analysis"]))
    coverage_result = CoverageResult(
        coverage_goals=validate_coverage_goals(data["coverage_goals"])
    )
    strategy_result = StrategyResult(
        coverage_items=validate_coverage_items(data["coverage_items"])
    )
    generate_result = GenerateResult(
        test_design_specs=validate_test_design_specs(data["test_design_specs"]),
        test_cases=validate_test_cases(data["test_cases"]),
    )
    return parse_result, risk_result, coverage_result, strategy_result, generate_result


async def _collect_stream_events(requirement_text: str):
    chunks = []
    async for chunk in runner.generate_blackbox_tests_stream(requirement_text, rag_context="标准上下文"):
        chunks.append(_parse_sse(chunk))
    return chunks


def _parse_sse(chunk: str) -> tuple[str, dict[str, Any]]:
    lines = [line for line in chunk.strip().splitlines() if line]
    event = lines[0].removeprefix("event: ")
    data = json.loads(lines[1].removeprefix("data: "))
    return event, data
