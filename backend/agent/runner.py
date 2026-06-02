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
    """同步入口：执行主流程并返回格式化结果。"""

    if not requirement_text or not requirement_text.strip():
        return format_error_result(
            "需求文本不能为空。",
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
        return format_error_result(exc.error, {"failed_step": exc.stage})
    except Exception as exc:
        return format_error_result(str(exc), {"failed_step": StageName.AGENT_RUNNER})


async def generate_blackbox_tests_stream(
    requirement_text: str,
    rag_context: str | None = None,
) -> AsyncIterator[str]:
    """流式入口：按阶段输出进度，单阶段失败不丢失已完成阶段的产出。"""

    if not requirement_text or not requirement_text.strip():
        yield _format_sse(
            "stage_error",
            _stage_error_payload(
                StageName.INPUT_VALIDATION,
                "需求文本不能为空。",
            ),
        )
        return

    pipeline = AgentPipeline()
    stage_results: dict[str, Any] = {}
    error_stage: str | None = None

    try:
        async for stage, result in _iter_pipeline_stages(pipeline, requirement_text, rag_context):
            stage_results[stage] = result
            yield _format_sse("stage", _stage_completed_payload(stage, result))
    except StageExecutionError as exc:
        error_stage = exc.stage
        yield _format_sse("stage_error", _stage_error_payload(exc.stage, exc.error))
    except Exception as exc:
        yield _format_sse(
            "stage_error",
            _stage_error_payload(StageName.AGENT_RUNNER, str(exc)),
        )
        return

    # Finalize: only if all 7 stages completed successfully
    required_stages = [
        StageName.PARSE_REQUIREMENTS,
        StageName.ANALYZE_RISK,
        StageName.IDENTIFY_COVERAGE,
        StageName.ASSIGN_STRATEGY,
        StageName.GENERATE_TESTS,
        StageName.GENERATE_FSM,
        StageName.GENERATE_ORACLE,
    ]
    if all(k in stage_results for k in required_stages):
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
                "final_output": final_result.model_dump(mode="json"),
            },
        )
    else:
        completed = list(stage_results.keys())
        yield _format_sse(
            "final",
            {
                "status": "partial",
                "completed_stages": completed,
                "error_stage": error_stage,
            },
        )


async def _iter_pipeline_stages(
    pipeline: AgentPipeline,
    requirement_text: str,
    rag_context: str | None,
) -> AsyncIterator[tuple[str, Any]]:
    """阶段式执行：每阶段完成即 yield，不阻塞后续阶段的 SSE 事件发布。"""

    # ---- Stage 1: Parse Requirements ----
    parse_result = await pipeline.parse_requirements(requirement_text, rag_context)
    yield StageName.PARSE_REQUIREMENTS, parse_result

    # ---- Stage 2: Analyze Risk ----
    risk_result = await pipeline.analyze_risk(parse_result.analyzed_requirements, rag_context)
    yield StageName.ANALYZE_RISK, risk_result

    # ---- Stage 3: Identify Coverage (yield immediately, before strategy) ----
    coverage_result = await pipeline.identify_coverage(
        parse_result.analyzed_requirements,
        risk_result.risk_analysis,
        rag_context,
    )
    yield StageName.IDENTIFY_COVERAGE, coverage_result

    # ---- Stage 4: Assign Strategy (yield immediately, before generate) ----
    strategy_result = await pipeline.assign_strategy(
        coverage_result.coverage_goals,
        parse_result.analyzed_requirements,
        risk_result.risk_analysis,
        rag_context,
    )
    yield StageName.ASSIGN_STRATEGY, strategy_result

    # ---- Stage 5a: Generate Tests + Stage 5b: FSM (parallel, after coverage/strategy yielded) ----
    fsm_task = asyncio.create_task(
        _run_fr4_branch(
            pipeline,
            parse_result.requirements,
            parse_result.analyzed_requirements,
            rag_context,
        )
    )

    generate_result = await pipeline.generate_tests(
        strategy_result.coverage_items,
        risk_result.risk_analysis,
        rag_context,
    )
    yield StageName.GENERATE_TESTS, generate_result

    fsm_result = await fsm_task
    yield StageName.GENERATE_FSM, fsm_result

    # ---- Stage 6: Oracle (depends on FR3 tests + FSM tests) ----
    merged_test_cases = _merge_test_cases(generate_result.test_cases, fsm_result.test_cases)
    oracle_result = await pipeline.generate_oracles(
        merged_test_cases,
        requirements=parse_result.analyzed_requirements,
        rag_context=rag_context,
    )
    yield StageName.GENERATE_ORACLE, oracle_result


async def _run_fr4_branch(
    pipeline: AgentPipeline,
    requirements: list,
    analyzed_requirements: list,
    rag_context: str | None,
) -> Any:
    """FR4 分支：FSM 建模。"""

    return await pipeline.generate_fsm(
        requirements=requirements,
        parsed_requirements=analyzed_requirements,
        rag_context=rag_context,
    )


def _merge_test_cases(fr3_cases: list, fr4_cases: list) -> list[dict[str, Any]]:
    """合并 FR3/FR4 用例，并打上来源标签供 FR5 使用。"""

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
    """统一 stage 完成事件的输出结构。"""

    return {
        "stage": stage,
        "title": STAGE_TITLES.get(stage, stage),
        "status": "completed",
        "output": _stage_output(output),
    }


def _stage_error_payload(stage: str, error: str) -> dict[str, str]:
    """统一 stage 失败事件的输出结构。"""

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
