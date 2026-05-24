from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.rag.chunker import MarkdownChunk


RAG_ROOT = Path(__file__).resolve().parent
DB_DIR = RAG_ROOT / "db"
DEFAULT_COLLECTION_NAME = "markdown_knowledge_base"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

try:
    import chromadb
except ImportError:  # pragma: no cover - 运行环境缺依赖时给出清晰提示
    chromadb = None


class ChromaVectorStore:
    """封装 ChromaDB 的持久化写入和检索。"""

    def __init__(
        self,
        persist_dir: Path | None = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_function: Any | None = None,
        recreate_collection: bool = False,
    ) -> None:
        if chromadb is None:
            raise RuntimeError("缺少 chromadb 依赖，请先在 backend 环境安装: pip install chromadb")

        self.persist_dir = persist_dir or DB_DIR
        self.collection_name = collection_name
        self.embedding_function = embedding_function or create_embedding_function()

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        if recreate_collection and self.collection_name in self._collection_names():
            self.client.delete_collection(self.collection_name)
        self.collection = self._get_or_create_collection()

    def reset_collection(self) -> None:
        """重建索引前清空旧 collection，避免已删除文档残留。"""

        if self.collection_name in self._collection_names():
            self.client.delete_collection(self.collection_name)
        self.collection = self._get_or_create_collection()

    def add_chunks(self, chunks: list[MarkdownChunk]) -> int:
        if not chunks:
            return 0

        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
        )
        return len(chunks)

    def query(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if top_k <= 0 or not query.strip():
            return []

        result = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        records: list[dict[str, Any]] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            score = max(0.0, 1.0 - float(distance))
            records.append(
                {
                    "text": document,
                    "metadata": metadata or {},
                    "distance": float(distance),
                    "score": score,
                }
            )

        return records

    def count(self) -> int:
        return self.collection.count()

    def _get_or_create_collection(self) -> Any:
        try:
            return self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        except ValueError as exc:
            if "Embedding function conflict" in str(exc):
                raise RuntimeError(
                    "检测到已有 ChromaDB collection 使用了不同的 embedding。"
                    "请运行 backend/rag/build_index.py 重建索引，或清空 backend/rag/db 后再建库。"
                ) from exc
            raise

    def _collection_names(self) -> set[str]:
        names: set[str] = set()
        for collection in self.client.list_collections():
            names.add(collection if isinstance(collection, str) else collection.name)
        return names


def create_embedding_function(model_name: str = DEFAULT_EMBEDDING_MODEL) -> Any:
    """创建正式语义检索 embedding。

    sentence-transformers 会优先使用本地路径或缓存模型；默认使用适合中文检索的 BGE 小模型。
    """

    if chromadb is None:
        raise RuntimeError("缺少 chromadb 依赖，请先在 backend 环境安装: pip install chromadb")

    try:
        import sentence_transformers  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "缺少 sentence-transformers 依赖，无法进行真实语义检索。"
            "请先在 backend 环境安装: pip install sentence-transformers"
        ) from exc

    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    return SentenceTransformerEmbeddingFunction(
        model_name=model_name,
        normalize_embeddings=True,
    )
