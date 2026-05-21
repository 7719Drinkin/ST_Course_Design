"""标准文档入库。

负责读取 backend/data/standards 下的测试标准文档，切分后写入 ChromaDB。
第一版支持 txt/md/pdf，PDF 使用 pymupdf。
"""

from __future__ import annotations

from pathlib import Path

from backend.rag_engine.vector_store import add_documents

STANDARDS_DIR = Path(__file__).resolve().parents[1] / "data" / "standards"


def read_standard_file(path: Path) -> str:
    """读取单个标准文档。"""
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".pdf":
        import fitz

        document = fitz.open(path)
        return "\n".join(page.get_text() for page in document)
    return ""


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """用简单滑动窗口切分文本，后续可替换为语义切分。"""
    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks


def ingest_standards() -> dict[str, int | str]:
    """把 standards 目录中的文档写入 ChromaDB。"""
    STANDARDS_DIR.mkdir(parents=True, exist_ok=True)
    documents: list[str] = []
    metadatas: list[dict[str, str | int]] = []
    for path in sorted(STANDARDS_DIR.glob("*")):
        text = read_standard_file(path)
        if not text:
            continue
        for index, chunk in enumerate(chunk_text(text)):
            documents.append(chunk)
            metadatas.append({"source": str(path), "chunk_index": index})
    result = add_documents(documents, metadatas=metadatas)
    return {"source_dir": str(STANDARDS_DIR), "chunks": result["added"]}
