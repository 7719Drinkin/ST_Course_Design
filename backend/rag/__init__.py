"""RAG (Retrieval-Augmented Generation) module — document ingestion, embedding,
vector storage, and semantic retrieval.

This package is intentionally isolated from `app/`. It can be tested, deployed,
or replaced independently. `app/` modules consume it through interfaces defined
here, never depending on its internal implementation.
"""
