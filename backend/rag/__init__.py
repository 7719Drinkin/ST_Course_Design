"""Backend 内部 RAG 模块。

agent 层只应从这里导入 RagService，不直接访问 loader/chunker/vector_store。
"""

from backend.rag.rag_service import RagService

__all__ = ["RagService"]
