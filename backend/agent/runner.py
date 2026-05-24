from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from .pipeline.agent_pipeline import AgentPipeline
from .tools.final_quality_gate import run_final_quality_gate
from .tools.result_formatter import format_error_result, format_success_result


async def generate_blackbox_tests(
    requirement_text: str,
    rag_context: str | None = None,
) -> dict[str, Any]:
    """对外唯一推荐入口：把需求文本转换为黑盒测试设计结果。

    这里负责输入校验、调用内部 AgentPipeline、执行最终质量门禁，
    并把内部 pipeline 的散落字段整理成稳定的对外 JSON。
    所有异常都会被转换成标准错误结构，避免调用方直接感知内部实现。
    """

    if not requirement_text or not requirement_text.strip():
        return format_error_result(
            "requirement_text is required.",
            {"failed_step": "input_validation"},
        )

    try:
        raw_result = await AgentPipeline().run(requirement_text, rag_context=rag_context)
        if raw_result.get("success") is not True:
            return format_error_result(str(raw_result.get("error", "Agent pipeline failed.")), raw_result)

        try:
            run_final_quality_gate(raw_result)
        except Exception as exc:
            return format_error_result(
                f"Final quality gate failed: {exc}",
                {**raw_result, "failed_step": "final_quality_gate"},
            )

        return format_success_result(raw_result, rag_context=rag_context)
    except Exception as exc:
        return format_error_result(str(exc), {"failed_step": "agent_runner"})


async def generate_blackbox_tests_stream(
    requirement_text: str,
    rag_context: str | None = None,
) -> AsyncIterator[str]:
    """以 SSE 文本片段流式返回完整 pipeline 的阶段进度。

    调用方仍然只提交一次 requirement_text；后端会连续执行完整流程，
    并在每个阶段完成后立即产出一条 SSE 事件。
    """

    if not requirement_text or not requirement_text.strip():
        yield _format_sse(
            "stage_error",
            {
                "stage": "input_validation",
                "status": "failed",
                "error": "requirement_text is required.",
            },
        )
        return

    try:
        pipeline = AgentPipeline()
        async for event in pipeline.run_stream(requirement_text, rag_context=rag_context):
            yield _format_sse(str(event.get("event", "stage")), event.get("data", {}))
    except Exception as exc:
        yield _format_sse(
            "stage_error",
            {
                "stage": "agent_runner",
                "status": "failed",
                "error": str(exc),
            },
        )


def _format_sse(event: str, data: dict[str, Any]) -> str:
    """把单个事件和 JSON 数据格式化为标准 SSE 消息。"""

    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
