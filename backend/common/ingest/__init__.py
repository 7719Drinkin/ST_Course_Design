"""Global text holder with multi-format ingest.

Usage::

    from backend.common.ingest import ingest_manager

    ingest_manager.ingest("doc.pdf")
    text = ingest_manager.load_text()
"""

from .manager import ingest_manager

__all__ = ["ingest_manager"]
