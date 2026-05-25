"""Step 1 business logic: requirement ingest and structural parsing."""

from pathlib import Path
from typing import Any

from common.ingest import ingest_manager

from ..util import to_dict
from ..store import workflow_store
from .schemas import ParseRequest, ParseResponse


class IntakeParseService:
    def ingest_text(self, content: str) -> None:
        ingest_manager.ingest(content.encode("utf-8"))

    def ingest_file(self, raw: bytes, filename: str) -> None:
        ext = Path(filename).suffix or ".txt"
        ingest_manager.ingest(raw, ext)

    def parse(self, request: ParseRequest) -> ParseResponse:
        """Structural parsing of requirements.

        TODO: 接入 B Agent 的 requirement parse Prompt。
              输入：session_id, requirement_ids, requirements
              输出：list[ParsedRequirement]（含 input_fields, data_ranges,
                    conditions, expected_action, confidence, missing_fields）
              现在 B Agent 未接入，直接返回空列表 + 错误占位。
        """
        requirements = self._load_requirements(request)
        if not requirements:
            return ParseResponse(
                session_id=request.session_id,
                parsed_requirements=[],
                prompt_evidence=[],
                errors=[],
            )

        workflow_store.save_many(request.session_id, "requirements", requirements, "requirement_id")
        return ParseResponse(
            session_id=request.session_id,
            parsed_requirements=[],
            prompt_evidence=[],
            errors=[],
        )

    def _load_requirements(self, request: ParseRequest) -> list[dict[str, Any]]:
        if request.requirements:
            return [to_dict(item) for item in request.requirements]

        stored = workflow_store.get_list(
            request.session_id,
            "requirements",
            request.requirement_ids,
            "requirement_id",
        )
        if stored:
            return stored

        ingested = ingest_manager.load_text()
        if not ingested.strip():
            return []
        # TODO: B Agent 接入后由 Prompt 拆分需求条目；当前直接整段作为一条需求。
        return [{"requirement_id": "REQ-AUT-001", "text": ingested.strip()}]
