from __future__ import annotations

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
