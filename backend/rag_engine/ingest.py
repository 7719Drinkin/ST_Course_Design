"""标准文档入库。

只读取 MinerU 解析后的 markdown 文件，
切分后写入 ChromaDB。
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any

from backend.rag_engine.vector_store import DEFAULT_COLLECTION_NAME, add_documents, delete_documents


# MinerU 输出目录
STANDARDS_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "standards"
    / "MinerU"
)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
PAGE_PATTERN = re.compile(r"\bPage\s+(\d+)\s+of\s+\d+\b", re.IGNORECASE)


@dataclass(frozen=True)
class TextChunk:
    """文本片段及其在原文中的字符位置。"""

    text: str
    start: int
    end: int
    index: int


@dataclass(frozen=True)
class MarkdownHeading:
    """用于推断 chunk metadata 的 Markdown 标题标记。"""

    position: int
    level: int
    title: str
    number_depth: int


@dataclass(frozen=True)
class PageMarker:
    """从 MinerU markdown 中解析出的页码标记。"""

    position: int
    page: int


def read_markdown_file(path: Path) -> str:
    """读取 markdown 文件。"""
    return path.read_text(encoding="utf-8")


def chunk_markdown(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[TextChunk]:
    """简单滑动窗口切分。"""

    chunks: list[TextChunk] = []

    start = 0
    step = max(1, chunk_size - overlap)
    index = 0

    while start < len(text):
        raw_chunk = text[start : start + chunk_size]
        chunk = raw_chunk.strip()

        if chunk:
            chunks.append(
                TextChunk(
                    text=chunk,
                    start=start + raw_chunk.find(chunk),
                    end=start + raw_chunk.find(chunk) + len(chunk),
                    index=index,
                )
            )
            index += 1

        start += step

    return chunks


def source_from_filename(path: Path) -> str:
    """从 MinerU markdown 文件名中提取稳定的 source 名称。"""
    source = path.stem
    source = re.sub(r"^MinerU_markdown_", "", source)
    source = re.sub(r"_\d{10,}$", "", source)
    return source


def make_chunk_id(source: str, chunk_index: int, chunk_text: str) -> str:
    """生成确定性的 chunk_id，保证重复入库时可幂等覆盖。"""
    digest = hashlib.sha1(f"{source}:{chunk_index}:{chunk_text}".encode("utf-8")).hexdigest()[:12]
    return f"{source}-{chunk_index:05d}-{digest}"


def collect_headings(text: str) -> list[MarkdownHeading]:
    """收集 Markdown 标题，并粗略推断数字标题层级。"""
    headings: list[MarkdownHeading] = []
    for match in HEADING_PATTERN.finditer(text):
        title = match.group(2).strip()
        number_match = re.match(r"^(\d+(?:\.\d+)*)\.?", title)
        number_depth = number_match.group(1).count(".") + 1 if number_match else 0
        headings.append(
            MarkdownHeading(
                position=match.start(),
                level=len(match.group(1)),
                title=title,
                number_depth=number_depth,
            )
        )
    return headings


def collect_page_markers(text: str) -> list[PageMarker]:
    """收集 MinerU markdown 中的页码标记。"""
    return [PageMarker(position=match.start(), page=int(match.group(1))) for match in PAGE_PATTERN.finditer(text)]


def infer_heading_metadata(headings: list[MarkdownHeading], offset: int) -> dict[str, str]:
    """根据 chunk 起始位置推断 chapter 和 section metadata。"""
    metadata: dict[str, str] = {}
    chapter = ""
    section = ""

    for heading in headings:
        if heading.position > offset:
            break
        if heading.number_depth and heading.number_depth <= 2:
            chapter = heading.title
            section = ""
        elif heading.number_depth and heading.number_depth > 2:
            section = heading.title
        elif heading.level <= 2:
            chapter = heading.title
            section = ""
        else:
            section = heading.title

    if chapter:
        metadata["chapter"] = chapter
    if section:
        metadata["section"] = section
    return metadata


def infer_page_metadata(page_markers: list[PageMarker], offset: int) -> dict[str, int]:
    """根据 chunk 前最近的页码标记推断 page metadata。"""
    page: int | None = None
    for marker in page_markers:
        if marker.position > offset:
            break
        page = marker.page
    return {"page": page} if page is not None else {}


def build_chunk_metadata(
    path: Path,
    chunk: TextChunk,
    headings: list[MarkdownHeading],
    page_markers: list[PageMarker],
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, str | int | float | bool]:
    """为单个 chunk 构造可扩展的 Chroma metadata。"""
    source = source_from_filename(path)
    chunk_id = make_chunk_id(source, chunk.index, chunk.text)
    metadata: dict[str, str | int | float | bool] = {
        "source": source,
        "source_file": path.name,
        "chunk_id": chunk_id,
        "chunk_index": chunk.index,
        "type": "testing_standard",
    }
    metadata.update(infer_heading_metadata(headings, chunk.start))
    metadata.update(infer_page_metadata(page_markers, chunk.start))
    if extra_metadata:
        for key, value in extra_metadata.items():
            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value
    return metadata


def ingest_standards(
    collection_name: str = DEFAULT_COLLECTION_NAME,
    extra_metadata: dict[str, Any] | None = None,
    replace_source: bool = True,
) -> dict[str, int | str]:
    """把 MinerU markdown 文档写入 ChromaDB。"""

    STANDARDS_DIR.mkdir(parents=True, exist_ok=True)

    documents: list[str] = []
    metadatas: list[dict[str, str | int | float | bool]] = []
    ids: list[str] = []

    # 只读取 md
    for path in sorted(STANDARDS_DIR.glob("*.md")):

        print(f"[INGEST] Loading {path.name}")

        text = read_markdown_file(path)
        source = source_from_filename(path)
        headings = collect_headings(text)
        page_markers = collect_page_markers(text)

        chunks = chunk_markdown(text)

        if replace_source:
            delete_documents({"source_file": path.name}, collection_name=collection_name)
            delete_documents({"source": path.name}, collection_name=collection_name)
            delete_documents({"source": source}, collection_name=collection_name)

        for chunk in chunks:
            metadata = build_chunk_metadata(
                path,
                chunk,
                headings,
                page_markers,
                extra_metadata=extra_metadata,
            )

            documents.append(chunk.text)
            metadatas.append(metadata)
            ids.append(str(metadata["chunk_id"]))

    result = add_documents(documents, metadatas=metadatas, ids=ids, collection_name=collection_name)

    return {
        "source_dir": str(STANDARDS_DIR),
        "collection": str(result["collection"]),
        "chunks": result["added"],
    }


if __name__ == "__main__":

    result = ingest_standards()

    print("\n===== INGEST FINISHED =====")
    print(result)
