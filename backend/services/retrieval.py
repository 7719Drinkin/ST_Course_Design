"""RAG 检索服务。

负责组织向量检索、调试日志输出，并为后续 rerank / metadata filter 扩展保留入口。
"""

from __future__ import annotations

from typing import Any

from backend.rag_engine.vector_store import similarity_search
from backend.utils.logging import format_retrieval_debug, get_logger

logger = get_logger("retrieval")


def retrieve_chunks(
    query: str,
    top_k: int = 5,
    where: dict[str, Any] | None = None,
    debug: bool = True,
) -> list[dict[str, Any]]:
    """从 ChromaDB 检索片段，并返回 API 可直接输出的结构。"""
    results = similarity_search(query=query, top_k=top_k, where=where)

    if debug:
        logger.info(format_retrieval_debug(query, results))

    return results
