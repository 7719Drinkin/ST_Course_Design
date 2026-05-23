import atexit
from pathlib import Path

from .parsers import (
    BaseParser,
    DocParser,
    DocxParser,
    PdfParser,
    TextParser,
)

_DEFAULT_PARSERS = (
    TextParser(),
    PdfParser(),
    DocxParser(),
    DocParser(),
)

_INGEST_FILE = Path(__file__).resolve().parent.parent.parent / "atd_ingest"


class IngestManager:
    """Orchestrates document ingestion and global text retrieval.
    Usage::
        manager = IngestManager()
        manager.ingest(raw_bytes, ext=".pdf")
        text = manager.load_text()
    """

    def __init__(self) -> None:
        self._parsers: dict[str, BaseParser] = {}
        # 注册解析器
        for p in _DEFAULT_PARSERS:
            for ext in p.extensions:
                self._parsers[ext] = p
        self._ext: str = ".txt"
        atexit.register(self.reset)

    # -- public --------------------------------------------------
    def ingest(self, raw: bytes, ext: str = ".txt") -> None:
        """Persist raw bytes with format hint."""
        self._ext = ext
        _INGEST_FILE.write_bytes(raw)

    def load_text(self) -> str:
        """Read raw bytes from file, parse, return text."""
        if not _INGEST_FILE.exists():
            return ""
        return self._parse(_INGEST_FILE.read_bytes(), self._ext)

    def reset(self) -> None:
        """Clear the file and reset state."""
        if _INGEST_FILE.exists():
            _INGEST_FILE.write_bytes(b"")
        self._ext = ".txt"

    # -- internal ------------------------------------------------
    def _parse(self, raw: bytes, hint: str) -> str:
        ext = hint.lower()
        parser = self._parsers.get(ext)
        if parser is not None:
            return parser.parse(raw)
        return raw.decode("utf-8", errors="replace")


# ── Module-level convenience instance ──────────────────────────
ingest_manager = IngestManager()
