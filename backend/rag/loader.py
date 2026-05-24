from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RAG_ROOT = Path(__file__).resolve().parent
DATA_DIR = RAG_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"


@dataclass(frozen=True)
class MarkdownDocument:
    """从 data/processed 读取出来的一篇 Markdown 文档。"""

    source: str
    path: Path
    content: str


def load_markdown_documents(processed_dir: Path | None = None) -> list[MarkdownDocument]:
    """读取 data/processed 下的所有 .md 文件。

    data/raw 只保存原始 PDF；RAG 建库只使用转换后的 Markdown。
    """

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    data_dir = processed_dir or PROCESSED_DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(path for path in data_dir.rglob("*") if path.is_file())
    invalid_files = [path for path in files if path.suffix.lower() != ".md"]
    if invalid_files:
        names = ", ".join(str(path.relative_to(data_dir)) for path in invalid_files)
        raise ValueError(f"backend/rag/data/processed 只允许存放 .md 文件: {names}")

    documents: list[MarkdownDocument] = []
    for path in files:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue

        source = path.relative_to(data_dir).as_posix()
        documents.append(MarkdownDocument(source=source, path=path, content=content))

    return documents
