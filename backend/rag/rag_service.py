from __future__ import annotations

from typing import Any

from .vector_store import ChromaVectorStore


class RagService:
    """agent 层唯一应该调用的 RAG 入口。"""

    def __init__(self, vector_store: ChromaVectorStore | None = None) -> None:
        self.vector_store = vector_store or ChromaVectorStore()

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """检索与 query 最相关的 Markdown chunk。"""

        clean_query = query.strip()
        if not clean_query:
            return []

        return self.vector_store.query(clean_query, top_k=top_k)
