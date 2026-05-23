"""RAG 检索入口。"""

from __future__ import annotations

from typing import Any

from backend.utils.config import DEFAULT_TOP_K
from backend.rag_engine.vector_store import query_documents


def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    """检索相关文档片段，统一返回 content / score / metadata。"""
    return query_documents(query=query, top_k=top_k)
