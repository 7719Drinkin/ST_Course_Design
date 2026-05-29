"""Step 1 business logic: requirement ingest and structural parsing."""

from pathlib import Path

from fastapi import HTTPException

from common.ingest import ingest_manager

from ..store import workflow_store
from ..util import (
    STAGE_PARSE,
    effective_rag_context,
    normalize_stage_output,
    parse_sse_event,
    prompt_records_to_evidence,
    save_requirement_input,
    stage_output_summary,
)
from .schemas import ParseRequest, ParseResponse

from agent import generate_blackbox_tests_stream


class IntakeParseService:
    def ingest_text(self, content: str) -> None:
        ingest_manager.ingest(content.encode("utf-8"))

    def ingest_file(self, raw: bytes, filename: str) -> None:
        ext = Path(filename).suffix or ".txt"
        ingest_manager.ingest(raw, ext)

    async def parse(self, request: ParseRequest) -> ParseResponse:
        requirement_text = self._resolve_requirement_text(request)
        if not requirement_text:
            return ParseResponse(
                requirements=[],
                analyzed_requirements=[],
                prompts_used=[],
            )
        save_requirement_input(request.session_id, requirement_text, request.rag_context)
        output = await _runner_parse_output(request.session_id, requirement_text, request.rag_context)
        return ParseResponse(
            requirements=output.get("requirements", []),
            analyzed_requirements=output.get("analyzed_requirements", []),
            prompts_used=output.get("prompts_used", []),
        )

    def _resolve_requirement_text(self, request: ParseRequest) -> str:
        requirement_text = request.requirement_text.strip()
        if requirement_text:
            return requirement_text
        return ingest_manager.load_text().strip()


async def _runner_parse_output(
    session_id: str,
    requirement_text: str,
    rag_context: str | None,
) -> dict:
    stream = generate_blackbox_tests_stream(
        requirement_text=requirement_text,
        rag_context=effective_rag_context(session_id, rag_context),
    )
    try:
        async for raw_event in stream:
            event, data = parse_sse_event(raw_event)
            if event == "stage" and data.get("stage") == STAGE_PARSE:
                output = normalize_stage_output(data.get("output") or {})
                _save_parse_output(session_id, output)
                return output
            if event == "stage_error":
                _raise_stage_error(data)
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            await aclose()
    raise HTTPException(status_code=502, detail="Runner did not emit parse_requirements stage")


def _save_parse_output(session_id: str, output: dict) -> None:
    workflow_store.save_many(
        session_id,
        "requirements",
        output.get("requirements", []),
        "requirement_id",
        replace_all=True,
    )
    analyzed_requirements = output.get("analyzed_requirements", [])
    workflow_store.save_many(
        session_id,
        "parsed_requirements",
        analyzed_requirements or output.get("requirements", []),
        "requirement_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "analyzed_requirements",
        analyzed_requirements,
        "requirement_id",
        replace_all=True,
    )
    prompt_evidence = prompt_records_to_evidence(
        session_id=session_id,
        records=output.get("prompts_used"),
        target_id="requirements",
        output_data=stage_output_summary(STAGE_PARSE, output),
        note="Agent runner stage parse_requirements prompt evidence.",
    )
    workflow_store.save_many(session_id, "prompt_evidence", prompt_evidence, "evidence_id")


def _raise_stage_error(data: dict) -> None:
    status = 400 if data.get("stage") == "input_validation" else 502
    raise HTTPException(status_code=status, detail=data.get("error") or "Agent runner stage failed")
