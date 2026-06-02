from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from rag.chunker import chunk_markdown_documents
    from rag.loader import load_markdown_documents
    from rag.vector_store import ChromaVectorStore
else:
    from .chunker import chunk_markdown_documents
    from .loader import load_markdown_documents
    from .vector_store import ChromaVectorStore


def build_index() -> tuple[int, int]:
    """Build the local RAG index from processed Markdown files."""

    documents = load_markdown_documents()
    chunks = chunk_markdown_documents(documents)

    vector_store = ChromaVectorStore(recreate_collection=True)
    vector_store.add_chunks(chunks)

    print(f"RAG index built: {len(documents)} Markdown files, {len(chunks)} chunks.")
    return len(documents), len(chunks)


if __name__ == "__main__":
    build_index()
