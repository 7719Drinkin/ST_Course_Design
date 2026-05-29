"""Step 3 business logic: coverage goals and strategy assignment."""

from __future__ import annotations

from fastapi import HTTPException

from ..store import workflow_store
from ..util import (
    STAGE_COVERAGE,
    STAGE_STRATEGY,
    effective_rag_context,
    normalize_stage_output,
    parse_sse_event,
    prompt_records_to_evidence,
    resolve_requirement_text,
    save_requirement_input,
    stage_output_summary,
)
from .schemas import (
    CoverageRequest,
    CoverageResponse,
    StrategyRequest,
    StrategyResponse,
)

from agent import generate_blackbox_tests_stream


class CoverageStrategyService:
    async def generate_coverage(self, request: CoverageRequest) -> CoverageResponse:
        requirement_text = resolve_requirement_text(
            session_id=request.session_id,
            explicit_text=request.requirement_text,
            fallback_payload={
                "analyzed_requirements": request.analyzed_requirements,
                "risk_analysis": request.risk_analysis,
            },
        )
        save_requirement_input(request.session_id, requirement_text, request.rag_context)
        output = await _runner_stage_output(
            request.session_id,
            requirement_text,
            request.rag_context,
            STAGE_COVERAGE,
        )
        return CoverageResponse(
            coverage_goals=output.get("coverage_goals", []),
            prompts_used=output.get("prompts_used", []),
        )

    async def assign_strategy(self, request: StrategyRequest) -> StrategyResponse:
        requirement_text = resolve_requirement_text(
            session_id=request.session_id,
            explicit_text=request.requirement_text,
            fallback_payload={
                "coverage_goals": request.coverage_goals,
                "analyzed_requirements": request.analyzed_requirements,
                "risk_analysis": request.risk_analysis,
            },
        )
        save_requirement_input(request.session_id, requirement_text, request.rag_context)
        output = await _runner_stage_output(
            request.session_id,
            requirement_text,
            request.rag_context,
            STAGE_STRATEGY,
        )
        return StrategyResponse(
            coverage_items=output.get("coverage_items", []),
            prompts_used=output.get("prompts_used", []),
        )


async def _runner_stage_output(
    session_id: str,
    requirement_text: str,
    rag_context: str | None,
    target_stage: str,
) -> dict:
    stream = generate_blackbox_tests_stream(
        requirement_text=requirement_text,
        rag_context=effective_rag_context(session_id, rag_context),
    )
    try:
        async for raw_event in stream:
            event, data = parse_sse_event(raw_event)
            if event == "stage" and data.get("stage") == target_stage:
                output = normalize_stage_output(data.get("output") or {})
                _save_stage_output(session_id, target_stage, output)
                return output
            if event == "stage_error":
                _raise_stage_error(data)
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            await aclose()
    raise HTTPException(status_code=502, detail=f"Runner did not emit {target_stage} stage")


def _save_stage_output(session_id: str, stage: str, output: dict) -> None:
    if stage == STAGE_COVERAGE:
        workflow_store.save_many(
            session_id,
            "coverage_goals",
            output.get("coverage_goals", []),
            "coverage_goal_id",
            replace_all=True,
        )
        target_id = "coverage_goals"
    else:
        workflow_store.save_many(
            session_id,
            "coverage_items",
            output.get("coverage_items", []),
            "coverage_item_id",
            replace_all=True,
        )
        target_id = "coverage_items"

    prompt_evidence = prompt_records_to_evidence(
        session_id=session_id,
        records=output.get("prompts_used"),
        target_id=target_id,
        output_data=stage_output_summary(stage, output),
        note=f"Agent runner stage {stage} prompt evidence.",
    )
    workflow_store.save_many(session_id, "prompt_evidence", prompt_evidence, "evidence_id")


def _raise_stage_error(data: dict) -> None:
    status = 400 if data.get("stage") == "input_validation" else 502
    raise HTTPException(status_code=status, detail=data.get("error") or "Agent runner stage failed")
