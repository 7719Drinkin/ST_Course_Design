import io
from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Abstract parser.  Subclass, set ``extensions``, implement ``parse``."""
    @property
    @abstractmethod
    def extensions(self) -> tuple[str, ...]:
        """File extensions this parser handles, e.g. ``(".txt", ".md")``."""

    @abstractmethod
    def parse(self, raw: bytes) -> str:
        """Parse *raw* bytes into clean text."""


# ── Built-in parsers ───────────────────────────────────────────
class TextParser(BaseParser):
    extensions = (".txt", ".md")

    def parse(self, raw: bytes) -> str:
        return raw.decode("utf-8", errors="replace")


class PdfParser(BaseParser):
    extensions = (".pdf",)

    def parse(self, raw: bytes) -> str:
        try:
            import pymupdf
        except ImportError:
            raise ImportError(
                "PDF support requires pymupdf. Run: pip install pymupdf"
            ) from None
        doc = pymupdf.open(stream=raw, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)


class DocxParser(BaseParser):
    extensions = (".docx",)

    def parse(self, raw: bytes) -> str:
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "DOCX support requires python-docx. Run: pip install python-docx"
            ) from None
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


class DocParser(BaseParser):
    extensions = (".doc",)

    def parse(self, raw: bytes) -> str:
        raise NotImplementedError(
            "Legacy .doc is not supported. Convert to .docx or .pdf first."
        )
