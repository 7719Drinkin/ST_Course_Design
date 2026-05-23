from pathlib import Path

from ....common.ingest import ingest_manager


class RequirementService:

    def ingest_text(self, content: str) -> None:
        ingest_manager.ingest(content.encode("utf-8"))

    def ingest_file(self, raw: bytes, filename: str) -> None:
        ext = Path(filename).suffix or ".txt"
        ingest_manager.ingest(raw, ext)
