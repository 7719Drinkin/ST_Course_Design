from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    # 支持直接运行: python backend/rag/build_index.py
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from backend.rag.chunker import chunk_markdown_documents
from backend.rag.loader import load_markdown_documents
from backend.rag.vector_store import ChromaVectorStore


def build_index() -> tuple[int, int]:
    """手动建库：读取 data/processed 中的 Markdown、切块、写入 ChromaDB。"""

    documents = load_markdown_documents()
    chunks = chunk_markdown_documents(documents)

    vector_store = ChromaVectorStore(recreate_collection=True)
    vector_store.add_chunks(chunks)

    print(f"RAG 索引构建完成：{len(documents)} 个 Markdown 文件，{len(chunks)} 个 chunk。")
    return len(documents), len(chunks)


if __name__ == "__main__":
    build_index()
