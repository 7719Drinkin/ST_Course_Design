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
from agent.tools.validation.id_gate import REQ_ID_RE, require_id_format, require_unique_ids


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
        run_id = workflow_store.start_pipeline_run(request.session_id)
        pipeline = AgentPipeline()
        pipeline_context = effective_rag_context(request.session_id, request.rag_context)
        try:
            parse_result = await _runner_parse_result(
                request.session_id,
                pipeline,
                requirement_text,
                pipeline_context,
            )
        except Exception as exc:
            workflow_store.fail_pipeline_run(
                request.session_id,
                run_id,
                "parse_requirements",
                str(exc),
            )
            raise
        workflow_store.complete_pipeline_stage(request.session_id, run_id, "parse_requirements", "analyze_risk")
        output = parse_result.model_dump(mode="json")
        output["prompts_used"] = normalize_prompt_records(output.get("prompts_used"))

        # Continue the same pipeline from the already returned parse_result.
        asyncio.create_task(
            _background_pipeline_after_parse(
                request.session_id,
                pipeline,
                parse_result,
                pipeline_context,
                run_id,
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

    require_id_format(parse_result.requirements, "requirement_id", REQ_ID_RE, "requirements")
    require_unique_ids(parse_result.requirements, "requirement_id", "requirements")
    require_id_format(
        parse_result.analyzed_requirements,
        "requirement_id",
        REQ_ID_RE,
        "analyzed_requirements",
    )
    require_unique_ids(
        parse_result.analyzed_requirements,
        "requirement_id",
        "analyzed_requirements",
    )
    requirement_ids = {item.requirement_id for item in parse_result.requirements}
    analyzed_ids = {item.requirement_id for item in parse_result.analyzed_requirements}
    if requirement_ids != analyzed_ids:
        missing = sorted(requirement_ids - analyzed_ids)
        extra = sorted(analyzed_ids - requirement_ids)
        raise ValueError(
            "analyzed_requirements must preserve parsed requirement IDs. "
            f"missing={missing or []}, extra={extra or []}"
        )
    output = parse_result.model_dump(mode="json")
    output["prompts_used"] = normalize_prompt_records(output.get("prompts_used"))
    _save_parse_output(session_id, output)
    return parse_result


def _save_parse_output(session_id: str, output: dict) -> None:
    workflow_store.clear_keys(
        session_id,
        [
            "risk_analysis",
            "risk_results",
            "coverage_goals",
            "coverage_items",
            "strategies",
            "test_design_specs",
            "test_cases",
            "fsm_test_cases",
            "prompt_evidence",
            "revisions",
            "analysis_results",
            "oracle_results",
            "optimization_result",
            "fsm",
        ],
    )
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
