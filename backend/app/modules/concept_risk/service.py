"""Step 2 business logic: risk scoring."""

from __future__ import annotations

from fastapi import HTTPException

from ..store import workflow_store
from ..util import (
    STAGE_RISK,
    effective_rag_context,
    normalize_stage_output,
    parse_sse_event,
    prompt_records_to_evidence,
    resolve_requirement_text,
    risk_analysis_to_risk_results,
    save_requirement_input,
    stage_output_summary,
)
from .schemas import RiskRequest, RiskResponse

try:
    from backend.agent import generate_blackbox_tests_stream
except ModuleNotFoundError:
    from agent import generate_blackbox_tests_stream


class ConceptRiskService:
    async def score_risk(self, request: RiskRequest) -> RiskResponse:
        requirement_text = resolve_requirement_text(
            session_id=request.session_id,
            explicit_text=request.requirement_text,
            fallback_payload=request.analyzed_requirements,
        )
        save_requirement_input(request.session_id, requirement_text, request.rag_context)
        output = await _runner_risk_output(request.session_id, requirement_text, request.rag_context)
        return RiskResponse(
            risk_analysis=output.get("risk_analysis", []),
            prompts_used=output.get("prompts_used", []),
        )


async def _runner_risk_output(
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
            if event == "stage" and data.get("stage") == STAGE_RISK:
                output = normalize_stage_output(data.get("output") or {})
                _save_risk_output(session_id, output)
                return output
            if event == "stage_error":
                _raise_stage_error(data)
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            await aclose()
    raise HTTPException(status_code=502, detail="Runner did not emit analyze_risk stage")


def _save_risk_output(session_id: str, output: dict) -> None:
    risk_analysis = output.get("risk_analysis", [])
    workflow_store.save_many(
        session_id,
        "risk_analysis",
        risk_analysis,
        "requirement_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "risk_results",
        risk_analysis_to_risk_results(risk_analysis),
        "target_id",
        replace_all=True,
    )
    prompt_evidence = prompt_records_to_evidence(
        session_id=session_id,
        records=output.get("prompts_used"),
        target_id="risk_analysis",
        output_data=stage_output_summary(STAGE_RISK, output),
        note="Agent runner stage analyze_risk prompt evidence.",
    )
    workflow_store.save_many(session_id, "prompt_evidence", prompt_evidence, "evidence_id")


def _raise_stage_error(data: dict) -> None:
    status = 400 if data.get("stage") == "input_validation" else 502
    raise HTTPException(status_code=status, detail=data.get("error") or "Agent runner stage failed")
