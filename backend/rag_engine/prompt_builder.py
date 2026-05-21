"""Prompt 拼接工具。

把需求、检索上下文和生成指令拼成统一 prompt，后续可保存到 DesignSession.prompts_used。
"""

from __future__ import annotations

from typing import Any


def build_prompt(requirement: str, retrieved_context: list[dict[str, Any]], instruction: str) -> str:
    """构建后续 LLM parse / risk / generate / oracle 可复用的 prompt。"""
    context_text = "\n\n".join(
        f"[{item.get('context_id', 'context')}] {item.get('text', '')}" for item in retrieved_context
    )
    return (
        "你是 AutoTestDesign 的测试设计助手。\n"
        "请严格基于需求和测试标准上下文输出结构化结果。\n\n"
        f"【需求】\n{requirement}\n\n"
        f"【标准上下文】\n{context_text or '暂无检索上下文'}\n\n"
        f"【任务指令】\n{instruction}\n"
    )
