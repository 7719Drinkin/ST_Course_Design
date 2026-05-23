"""RAG 检索服务。"""

from __future__ import annotations

from typing import Any

from backend.utils.config import DEFAULT_TOP_K
from backend.utils.logging import format_retrieval_debug, get_logger
from backend.rag_engine.retriever import retrieve

logger = get_logger("retrieval")


def retrieve_chunks(query: str, top_k: int = DEFAULT_TOP_K, debug: bool = True) -> list[dict[str, Any]]:
    """检索片段，并按需输出 retrieval debug 日志。"""
    results = retrieve(query=query, top_k=top_k)

    if debug:
        logger.info(format_retrieval_debug(query, results))

    return results
