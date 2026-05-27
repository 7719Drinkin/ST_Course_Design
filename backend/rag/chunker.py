from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .loader import MarkdownDocument


@dataclass(frozen=True)
class MarkdownChunk:
    """写入向量库的最小检索单元。"""

    id: str
    text: str
    metadata: dict[str, Any]


def chunk_markdown_documents(
    documents: list[MarkdownDocument],
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[MarkdownChunk]:
    """把 Markdown 文档切成带来源信息的 chunk。"""

    chunks: list[MarkdownChunk] = []
    for document in documents:
        for index, text in enumerate(chunk_markdown_text(document.content, chunk_size, overlap)):
            chunk_id = _build_chunk_id(document.source, index, text)
            chunks.append(
                MarkdownChunk(
                    id=chunk_id,
                    text=text,
                    metadata={
                        "source": document.source,
                        "chunk_index": index,
                    },
                )
            )

    return chunks


def chunk_markdown_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """按段落切分 Markdown，超长段落再按固定窗口切分。"""

    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if overlap < 0:
        raise ValueError("overlap 不能小于 0")
    if overlap >= chunk_size:
        raise ValueError("overlap 必须小于 chunk_size")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    blocks = [block.strip() for block in re.split(r"\n{2,}", normalized) if block.strip()]
    chunks: list[str] = []
    current = ""

    for block in blocks:
        if len(block) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_block(block, chunk_size, overlap))
            continue

        if not current:
            current = block
            continue

        candidate = f"{current}\n\n{block}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        chunks.append(current)
        current = _join_with_overlap(current, block, chunk_size, overlap)

    if current:
        chunks.append(current)

    return chunks


def _split_long_block(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = end - overlap

    return [chunk for chunk in chunks if chunk]


def _join_with_overlap(previous: str, block: str, chunk_size: int, overlap: int) -> str:
    if overlap == 0:
        return block

    # 保留上一块末尾少量上下文，减少跨段检索时的信息断裂。
    tail = previous[-overlap:].strip()
    candidate = f"{tail}\n\n{block}" if tail else block
    return candidate if len(candidate) <= chunk_size else block


def _build_chunk_id(source: str, index: int, text: str) -> str:
    digest = hashlib.sha1(f"{source}:{index}:{text}".encode("utf-8")).hexdigest()
    return f"{source}:{index}:{digest[:12]}"
