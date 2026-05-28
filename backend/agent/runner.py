from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from .pipeline.agent_pipeline import AgentPipeline
from .pipeline.errors import StageExecutionError
from .pipeline.finalizer import finalize_pipeline_result
from .pipeline.stages import STAGE_TITLES, StageName
from .tools.formatting.result_formatter import format_error_result, format_success_result


async def generate_blackbox_tests(
    requirement_text: str,
    rag_context: str | None = None,
) -> dict[str, Any]:
    """Synchronous entry: run stages, finalize, and format the response."""

    if not requirement_text or not requirement_text.strip():
        return format_error_result(
            "requirement_text is required.",
            {"failed_step": StageName.INPUT_VALIDATION},
        )

    pipeline = AgentPipeline()
    stage_results: dict[str, Any] = {}

    try:
        async for stage, result in _iter_pipeline_stages(pipeline, requirement_text, rag_context):
            stage_results[stage] = result

        final_result = finalize_pipeline_result(
            stage_results[StageName.PARSE_REQUIREMENTS],
            stage_results[StageName.ANALYZE_RISK],
            stage_results[StageName.IDENTIFY_COVERAGE],
            stage_results[StageName.ASSIGN_STRATEGY],
            stage_results[StageName.GENERATE_TESTS],
            stage_results[StageName.GENERATE_FSM],
            stage_results[StageName.GENERATE_ORACLE],
        )
        return format_success_result(
            {"success": True, **final_result.model_dump(mode="json")},
            rag_context=rag_context,
        )
    except StageExecutionError as exc:
        return format_error_result(
            exc.error,
            {"failed_step": exc.stage},
        )
    except Exception as exc:
        return format_error_result(str(exc), {"failed_step": StageName.AGENT_RUNNER})


async def generate_blackbox_tests_stream(
    requirement_text: str,
    rag_context: str | None = None,
) -> AsyncIterator[str]:
    """Streaming entry: emit each stage output and final payload."""

    if not requirement_text or not requirement_text.strip():
        yield _format_sse(
            "stage_error",
            _stage_error_payload(
                StageName.INPUT_VALIDATION,
                "requirement_text is required.",
            ),
        )
        return

    pipeline = AgentPipeline()
    stage_results: dict[str, Any] = {}

    try:
        async for stage, result in _iter_pipeline_stages(pipeline, requirement_text, rag_context):
            stage_results[stage] = result
            yield _format_sse("stage", _stage_completed_payload(stage, result))

        final_result = finalize_pipeline_result(
            stage_results[StageName.PARSE_REQUIREMENTS],
            stage_results[StageName.ANALYZE_RISK],
            stage_results[StageName.IDENTIFY_COVERAGE],
            stage_results[StageName.ASSIGN_STRATEGY],
            stage_results[StageName.GENERATE_TESTS],
            stage_results[StageName.GENERATE_FSM],
            stage_results[StageName.GENERATE_ORACLE],
        )
        yield _format_sse(
            "stage",
            _stage_completed_payload(StageName.FINAL_VALIDATION, {"passed": True}),
        )
        yield _format_sse(
            "final",
            {
                "status": "completed",
                "final_output": {
                    "test_cases": [test_case.model_dump(mode="json") for test_case in final_result.test_cases],
                    "fsm_test_cases": [
                        test_case.model_dump(mode="json") for test_case in final_result.fsm_test_cases
                    ],
                    "all_test_cases": [
                        test_case.model_dump(mode="json") for test_case in final_result.all_test_cases
                    ],
                    "oracle_results": [
                        oracle_item.model_dump(mode="json") for oracle_item in final_result.oracle_results
                    ],
                },
            },
        )
    except StageExecutionError as exc:
        yield _format_sse("stage_error", _stage_error_payload(exc.stage, exc.error))
    except Exception as exc:
        yield _format_sse(
            "stage_error",
            _stage_error_payload(StageName.AGENT_RUNNER, str(exc)),
        )


async def _iter_pipeline_stages(
    pipeline: AgentPipeline,
    requirement_text: str,
    rag_context: str | None,
) -> AsyncIterator[tuple[str, Any]]:
    """Single source of truth for the internal stage orchestration."""

    parse_result = await pipeline.parse_requirements(requirement_text, rag_context)
    yield StageName.PARSE_REQUIREMENTS, parse_result

    risk_result = await pipeline.analyze_risk(parse_result.analyzed_requirements, rag_context)
    yield StageName.ANALYZE_RISK, risk_result

    fr3_result, fsm_result = await asyncio.gather(
        _run_fr3_branch(
            pipeline,
            parse_result.analyzed_requirements,
            risk_result.risk_analysis,
            rag_context,
        ),
        _run_fr4_branch(
            pipeline,
            parse_result.requirements,
            parse_result.analyzed_requirements,
            rag_context,
        ),
    )

    yield StageName.IDENTIFY_COVERAGE, fr3_result[0]
    yield StageName.ASSIGN_STRATEGY, fr3_result[1]
    yield StageName.GENERATE_TESTS, fr3_result[2]
    yield StageName.GENERATE_FSM, fsm_result

    merged_test_cases = _merge_test_cases(fr3_result[2].test_cases, fsm_result.test_cases)
    oracle_result = await pipeline.generate_oracles(
        merged_test_cases,
        requirements=parse_result.analyzed_requirements,
        rag_context=rag_context,
    )
    yield StageName.GENERATE_ORACLE, oracle_result


async def _run_fr3_branch(
    pipeline: AgentPipeline,
    analyzed_requirements: list,
    risk_analysis: list,
    rag_context: str | None,
) -> tuple[Any, Any, Any]:
    coverage_result = await pipeline.identify_coverage(
        analyzed_requirements,
        risk_analysis,
        rag_context,
    )
    strategy_result = await pipeline.assign_strategy(
        coverage_result.coverage_goals,
        analyzed_requirements,
        risk_analysis,
        rag_context,
    )
    generate_result = await pipeline.generate_tests(
        strategy_result.coverage_items,
        risk_analysis,
        rag_context,
    )
    return coverage_result, strategy_result, generate_result


async def _run_fr4_branch(
    pipeline: AgentPipeline,
    requirements: list,
    analyzed_requirements: list,
    rag_context: str | None,
) -> Any:
    return await pipeline.generate_fsm(
        requirements=requirements,
        parsed_requirements=analyzed_requirements,
        rag_context=rag_context,
    )


def _merge_test_cases(fr3_cases: list, fr4_cases: list) -> list[dict[str, Any]]:
    merged_cases: list[dict[str, Any]] = []

    for test_case in fr3_cases:
        payload = test_case.model_dump(mode="json")
        payload["test_source"] = "FR3"
        merged_cases.append(payload)

    for test_case in fr4_cases:
        payload = test_case.model_dump(mode="json")
        payload["test_source"] = "FR4"
        merged_cases.append(payload)

    return merged_cases


def _stage_completed_payload(stage: str, output: Any) -> dict[str, Any]:
    return {
        "stage": stage,
        "title": STAGE_TITLES.get(stage, stage),
        "status": "completed",
        "output": _stage_output(output),
    }


def _stage_error_payload(stage: str, error: str) -> dict[str, str]:
    return {
        "stage": stage,
        "status": "failed",
        "error": error,
    }


def _format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stage_output(output: Any) -> Any:
    if isinstance(output, BaseModel):
        return output.model_dump(mode="json")
    return output
