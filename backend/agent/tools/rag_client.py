from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path
from typing import Any


class RAGClient:
    """agent 层对同级 rag 包的薄适配，不负责实现向量库。"""

    def __init__(self, rag_service: Any | None = None) -> None:
        """允许注入已有 RAG 服务，默认懒加载同级 rag.RagService。"""

        self._rag_service = rag_service

    async def retrieve(self, query: str, top_k: int = 5) -> str:
        """执行 RAG 检索，并把结果统一整理成 prompt 可用的文本上下文。"""

        if not query.strip():
            raise ValueError("RAG query is empty.")

        service = self._get_rag_service()
        retrieve = getattr(service, "retrieve", None)
        if retrieve is None:
            raise RuntimeError("RAG service is not available. Please connect backend RAG service first.")

        if inspect.iscoroutinefunction(retrieve):
            result = await retrieve(query, top_k=top_k)
        else:
            result = await asyncio.to_thread(retrieve, query, top_k)

        return self._format_context(result)

    def _get_rag_service(self) -> Any:
        """获取与 agent 同级的 rag.RagService；缺失时给出明确错误。"""

        if self._rag_service is not None:
            return self._rag_service

        try:
            self._ensure_sibling_rag_importable()
            from rag import RagService
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "RAG service is not available. Please connect backend RAG service first."
            ) from exc

        self._rag_service = RagService()
        return self._rag_service

    def _ensure_sibling_rag_importable(self) -> None:
        """确保优先导入 backend 下与 agent 同级的 rag 包。"""

        backend_dir = Path(__file__).resolve().parents[2]
        project_root = backend_dir.parent
        for path in (project_root, backend_dir):
            path_text = str(path)
            if path_text not in sys.path:
                sys.path.insert(0, path_text)

    def _format_context(self, result: Any) -> str:
        """把 RAG 的多种可能返回形态统一压成非空字符串。"""

        if isinstance(result, str):
            context = result.strip()
        elif isinstance(result, list):
            context = "\n\n".join(
                self._format_record(index, record)
                for index, record in enumerate(result, start=1)
            ).strip()
        elif isinstance(result, dict):
            records = result.get("results") or result.get("items")
            if isinstance(records, list):
                context = "\n\n".join(
                    self._format_record(index, record)
                    for index, record in enumerate(records, start=1)
                ).strip()
            else:
                context = self._format_record(1, result).strip()
        else:
            context = str(result).strip()

        if not context:
            raise RuntimeError("RAG service returned empty context.")
        return context

    def _format_record(self, index: int, record: Any) -> str:
        """把单条检索结果格式化为含 source/score/content 的可读片段。"""

        if not isinstance(record, dict):
            return f"[RAG Result {index}]\ncontent: {record}"

        metadata = record.get("metadata") or {}
        title = record.get("title") or metadata.get("title") or ""
        source = record.get("source") or metadata.get("source") or metadata.get("file") or ""
        content = (
            record.get("content")
            or record.get("text")
            or record.get("document")
            or record.get("page_content")
            or ""
        )
        score = record.get("score")
        distance = record.get("distance")

        lines = [f"[RAG Result {index}]"]
        if title:
            lines.append(f"title: {title}")
        if source:
            lines.append(f"source: {source}")
        if score is not None:
            lines.append(f"score: {score}")
        if distance is not None:
            lines.append(f"distance: {distance}")
        lines.append(f"content: {content}")
        return "\n".join(lines)
