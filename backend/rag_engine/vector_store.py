"""ChromaDB 向量库封装。

本文件只处理向量库读写，不直接调用前端，也不混入业务服务逻辑。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

CHROMA_DB_DIR = Path(__file__).resolve().parents[1] / "chroma_db"


def get_collection(collection_name: str = "testing_standards") -> Any:
    """获取 ChromaDB collection。"""
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    return client.get_or_create_collection(collection_name)


def add_documents(
    documents: list[str],
    metadatas: list[dict[str, Any]] | None = None,
    ids: list[str] | None = None,
    collection_name: str = "testing_standards",
) -> dict[str, int | str]:
    """向 ChromaDB 写入文档片段。"""
    if not documents:
        return {"collection": collection_name, "added": 0}
    collection = get_collection(collection_name)
    safe_ids = ids or [str(uuid4()) for _ in documents]
    safe_metadatas = metadatas or [{} for _ in documents]
    collection.add(documents=documents, metadatas=safe_metadatas, ids=safe_ids)
    return {"collection": collection_name, "added": len(documents)}


def similarity_search(query: str, top_k: int = 5, collection_name: str = "testing_standards") -> list[dict[str, Any]]:
    """根据查询文本检索相关标准片段。"""
    if not query.strip():
        return []
    collection = get_collection(collection_name)
    result = collection.query(query_texts=[query], n_results=top_k)
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]
    return [
        {
            "context_id": ids[index] if index < len(ids) else "",
            "text": document,
            "metadata": metadatas[index] if index < len(metadatas) else {},
        }
        for index, document in enumerate(documents)
    ]
