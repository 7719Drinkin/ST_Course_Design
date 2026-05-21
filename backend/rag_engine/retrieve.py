"""测试标准片段检索。

services 后续可以通过本模块根据需求文本或测试技术关键词检索标准上下文。
"""

from __future__ import annotations

from typing import Any

from backend.rag_engine.vector_store import similarity_search


def retrieve_context(requirement_text: str, technique: str | None = None, top_k: int = 5) -> list[dict[str, Any]]:
    """检索与需求和测试技术相关的标准片段。"""
    query = f"{requirement_text}\n{technique or ''}".strip()
    return similarity_search(query, top_k=top_k)
