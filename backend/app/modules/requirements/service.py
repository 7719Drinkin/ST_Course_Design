"""Requirement ingest service."""

import tempfile
from pathlib import Path

from ....common.ingest import ingest_manager


class RequirementService:

    def ingest(self, content: str, filename: str | None = None) -> str:
        """Write *content* to a temp file, pipe through ingest, return parsed text."""
        suffix = Path(filename).suffix if filename else ".txt"
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            prefix="atd_upload_",
            encoding="utf-8",
            delete=False,
        ) as f:
            f.write(content)
            tmp_path = f.name

        try:
            ingest_manager.ingest(tmp_path)
            return ingest_manager.load_text()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
