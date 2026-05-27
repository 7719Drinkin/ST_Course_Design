"""Step 1 business logic: requirement ingest and structural parsing."""

from pathlib import Path

from common.ingest import ingest_manager

from .schemas import ParseRequest, ParseResponse


class IntakeParseService:
    def ingest_text(self, content: str) -> None:
        ingest_manager.ingest(content.encode("utf-8"))

    def ingest_file(self, raw: bytes, filename: str) -> None:
        ext = Path(filename).suffix or ".txt"
        ingest_manager.ingest(raw, ext)

    def parse(self, request: ParseRequest) -> ParseResponse:
        """执行 RequirementParseAgent 和 RequirementAnalysisAgent。

        TODO: 接入 B Agent 的 RequirementParseAgent 和 RequirementAnalysisAgent。
              输入：requirement_text, rag_context
              输出：list[ParsedRequirement] + list[AnalyzedRequirement]
        """
        return ParseResponse(
            requirements=[],
            analyzed_requirements=[],
            prompts_used=[],
        )
