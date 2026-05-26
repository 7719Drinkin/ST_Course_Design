from __future__ import annotations

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
    """对外同步入口：校验输入、串联阶段、调用 finalizer、格式化响应。"""

    if not requirement_text or not requirement_text.strip():
        return format_error_result(
            "requirement_text is required.",
            {"failed_step": StageName.INPUT_VALIDATION},
        )

    pipeline = AgentPipeline()
    stage_results: dict[str, Any] = {}

    try:
        # 普通模式不直接碰 role agent，也不做字段校验；这里只按固定顺序串联阶段。
        async for stage, result in _iter_pipeline_stages(pipeline, requirement_text, rag_context):
            stage_results[stage] = result

        final_result = finalize_pipeline_result(
            stage_results[StageName.PARSE_REQUIREMENTS],
            stage_results[StageName.ANALYZE_RISK],
            stage_results[StageName.IDENTIFY_COVERAGE],
            stage_results[StageName.ASSIGN_STRATEGY],
            stage_results[StageName.GENERATE_TESTS],
        )
        return format_success_result(
            {"success": True, **final_result.model_dump()},
            rag_context=rag_context,
        )
    except StageExecutionError as exc:
        # 阶段异常保留真实 failed_step，partial_result 仅用于错误页调试，不参与业务补字段。
        return format_error_result(
            exc.error,
            {"failed_step": exc.stage},
        )
    except Exception as exc:
        # 未知异常统一归属 agent_runner，避免暴露内部文件结构给 API 调用方。
        return format_error_result(str(exc), {"failed_step": StageName.AGENT_RUNNER})


async def generate_blackbox_tests_stream(
    requirement_text: str,
    rag_context: str | None = None,
) -> AsyncIterator[str]:
    """对外流式入口：每个阶段完成立即发 SSE，最终校验通过后再发 final。"""

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
        )
        # final_validation 是独立阶段事件；通过后才允许发送最终 final 事件。
        yield _format_sse(
            "stage",
            _stage_completed_payload(StageName.FINAL_VALIDATION, {"passed": True}),
        )
        yield _format_sse(
            "final",
            {
                "status": "completed",
                "final_output": {
                    "test_cases": [test_case.model_dump() for test_case in final_result.test_cases]
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
    """完整 workflow 的唯一阶段顺序定义，普通和流式入口都复用这里。"""

    parse_result = await pipeline.parse_requirements(requirement_text, rag_context)
    yield StageName.PARSE_REQUIREMENTS, parse_result

    risk_result = await pipeline.analyze_risk(parse_result.analyzed_requirements, rag_context)
    yield StageName.ANALYZE_RISK, risk_result

    coverage_result = await pipeline.identify_coverage(
        parse_result.analyzed_requirements,
        risk_result.risk_analysis,
        rag_context,
    )
    yield StageName.IDENTIFY_COVERAGE, coverage_result

    strategy_result = await pipeline.assign_strategy(
        coverage_result.coverage_goals,
        parse_result.analyzed_requirements,
        risk_result.risk_analysis,
        rag_context,
    )
    yield StageName.ASSIGN_STRATEGY, strategy_result

    generate_result = await pipeline.generate_tests(
        strategy_result.coverage_items,
        risk_result.risk_analysis,
        rag_context,
    )
    yield StageName.GENERATE_TESTS, generate_result


def _stage_completed_payload(stage: str, output: Any) -> dict[str, Any]:
    """统一 stage completed 事件格式，保证普通阶段和 final_validation 一致。"""

    return {
        "stage": stage,
        "title": STAGE_TITLES.get(stage, stage),
        "status": "completed",
        "output": _stage_output(output),
    }


def _stage_error_payload(stage: str, error: str) -> dict[str, str]:
    """统一 stage_error 事件格式，错误阶段名只使用 StageName。"""

    return {
        "stage": stage,
        "status": "failed",
        "error": error,
    }


def _format_sse(event: str, data: dict[str, Any]) -> str:
    """把单个事件和 JSON 数据格式化为标准 SSE 消息。"""

    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stage_output(output: Any) -> Any:
    """阶段事件只接受新模型结果；这里明确用 model_dump 输出给 SSE。"""

    if isinstance(output, BaseModel):
        return output.model_dump()
    return output
