"""Step 1 business logic: requirement ingest and structural parsing."""

import asyncio
from pathlib import Path

from fastapi import HTTPException

from common.ingest import ingest_manager

from ..pipeline_bg import _background_pipeline_after_parse
from ..store import workflow_store
from ..util import (
    STAGE_PARSE,
    effective_rag_context,
    normalize_prompt_records,
    prompt_records_to_evidence,
    save_requirement_input,
    stage_output_summary,
)
from .schemas import ParseRequest, ParseResponse

from agent import AgentPipeline
from agent.core.models import ParseResult
from agent.pipeline.errors import StageExecutionError


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
        pipeline = AgentPipeline()
        pipeline_context = effective_rag_context(request.session_id, request.rag_context)
        parse_result = await _runner_parse_result(
            request.session_id,
            pipeline,
            requirement_text,
            pipeline_context,
        )
        output = parse_result.model_dump(mode="json")
        output["prompts_used"] = normalize_prompt_records(output.get("prompts_used"))

        # Continue the same pipeline from the already returned parse_result.
        asyncio.create_task(
            _background_pipeline_after_parse(
                request.session_id,
                pipeline,
                parse_result,
                pipeline_context,
            )
        )

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


async def _runner_parse_result(
    session_id: str,
    pipeline: AgentPipeline,
    requirement_text: str,
    rag_context: str | None,
) -> ParseResult:
    try:
        parse_result = await pipeline.parse_requirements(requirement_text, rag_context)
    except StageExecutionError as exc:
        _raise_stage_error({"stage": exc.stage, "error": exc.error})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    _normalize_parse_result_ids(parse_result)
    output = parse_result.model_dump(mode="json")
    output["prompts_used"] = normalize_prompt_records(output.get("prompts_used"))
    _save_parse_output(session_id, output)
    return parse_result


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


def _normalize_parse_result_ids(parse_result: ParseResult) -> None:
    """Normalize the parse_result object used by both frontend response and background stages."""

    id_map: dict[str, str] = {}
    for index, requirement in enumerate(parse_result.requirements, start=1):
        old_id = str(requirement.requirement_id or "")
        new_id = f"REQ-AUT-{index:03d}"
        if old_id:
            id_map[old_id] = new_id
        requirement.requirement_id = new_id

    for index, requirement in enumerate(parse_result.analyzed_requirements, start=1):
        old_id = str(requirement.requirement_id or "")
        requirement.requirement_id = id_map.get(old_id, f"REQ-AUT-{index:03d}")


def _raise_stage_error(data: dict) -> None:
    status = 400 if data.get("stage") == "input_validation" else 502
    raise HTTPException(status_code=status, detail=data.get("error") or "Agent runner stage failed")
