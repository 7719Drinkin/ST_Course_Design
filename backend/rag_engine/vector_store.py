"""ChromaDB 向量库封装。

本文件只处理向量库读写，不直接调用前端，也不混入业务服务逻辑。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

CHROMA_DB_DIR = Path(__file__).resolve().parents[1] / "chroma_db"
DEFAULT_COLLECTION_NAME = "testing_standards"


def get_collection(collection_name: str = DEFAULT_COLLECTION_NAME) -> Any:
    """获取 ChromaDB collection。"""
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    return client.get_or_create_collection(collection_name)


def add_documents(
    documents: list[str],
    metadatas: list[dict[str, Any]] | None = None,
    ids: list[str] | None = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> dict[str, int | str]:
    """向 ChromaDB 写入文档片段。"""
    if not documents:
        return {"collection": collection_name, "added": 0}
    collection = get_collection(collection_name)
    safe_ids = ids or [str(uuid4()) for _ in documents]
    safe_metadatas = metadatas or [{} for _ in documents]
    collection.upsert(documents=documents, metadatas=safe_metadatas, ids=safe_ids)
    return {"collection": collection_name, "added": len(documents)}


def delete_documents(
    where: dict[str, Any],
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> dict[str, str]:
    """删除匹配 metadata 过滤条件的文档片段。"""
    collection = get_collection(collection_name)
    collection.delete(where=where)
    return {"collection": collection_name, "deleted": "unknown"}


def _distance_to_score(distance: float | int | None) -> float | None:
    """把 Chroma distance 转成 0 到 1 之间的相似度观察分数。"""
    if distance is None:
        return None
    return 1 / (1 + float(distance))


def similarity_search(
    query: str,
    top_k: int = 5,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """根据查询文本检索相关标准片段。"""
    if not query.strip():
        return []
    collection = get_collection(collection_name)
    result = collection.query(query_texts=[query], n_results=top_k, where=where)
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    results: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        metadata = dict(metadatas[index] if index < len(metadatas) and metadatas[index] else {})
        if index < len(ids) and ids[index]:
            metadata.setdefault("chunk_id", ids[index])
        results.append(
            {
                "content": document,
                "score": _distance_to_score(distances[index] if index < len(distances) else None),
                "metadata": metadata,
            }
        )
    return results
