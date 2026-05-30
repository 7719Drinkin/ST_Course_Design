"""Background pipeline runner — consumes full SSE stream and writes each stage to WorkflowStore.

Called by intake_parse/service.py after /parse returns.  No new routes; no circular imports.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .store import workflow_store
from .util import (
    STAGE_COVERAGE,
    STAGE_FSM,
    STAGE_GENERATE,
    STAGE_ORACLE,
    STAGE_PARSE,
    STAGE_RISK,
    STAGE_STRATEGY,
    effective_rag_context,
    normalize_stage_output,
    parse_sse_event,
    prompt_records_to_evidence,
    risk_analysis_to_risk_results,
    stage_output_summary,
)

from agent import generate_blackbox_tests_stream

logger = logging.getLogger(__name__)


async def _background_full_pipeline(
    session_id: str,
    requirement_text: str,
    rag_context: str | None,
) -> None:
    """Run every pipeline stage in the background and persist results to WorkflowStore."""
    try:
        stream = generate_blackbox_tests_stream(
            requirement_text=requirement_text,
            rag_context=effective_rag_context(session_id, rag_context),
        )
        try:
            async for raw_event in stream:
                event, data = parse_sse_event(raw_event)
                if event == "stage":
                    stage = str(data.get("stage", ""))
                    output = normalize_stage_output(data.get("output") or {})
                    _dispatch_save(session_id, stage, output)
                    logger.debug("Background pipeline: saved stage %s for %s", stage, session_id)
                elif event == "stage_error":
                    logger.warning("Background pipeline stage_error: %s", data)
                elif event == "final":
                    logger.info("Background pipeline completed for session %s", session_id)
        finally:
            aclose = getattr(stream, "aclose", None)
            if aclose is not None:
                await aclose()
    except Exception:
        logger.exception("Background pipeline failed for session %s", session_id)


def _dispatch_save(session_id: str, stage: str, output: dict[str, Any]) -> None:
    """Write stage output to WorkflowStore based on stage name."""
    if stage == STAGE_PARSE:
        _save_parse(session_id, output)
    elif stage == STAGE_RISK:
        _save_risk(session_id, output)
    elif stage == STAGE_COVERAGE:
        _save_coverage(session_id, output)
    elif stage == STAGE_STRATEGY:
        _save_strategy(session_id, output)
    elif stage == STAGE_GENERATE:
        _save_generate(session_id, output)
    elif stage == STAGE_FSM:
        _save_fsm(session_id, output)
    elif stage == STAGE_ORACLE:
        _save_oracle(session_id, output)


# ---------------------------------------------------------------------------
# per-stage save helpers (inlined to avoid circular imports)
# ---------------------------------------------------------------------------

def _save_parse(session_id: str, output: dict[str, Any]) -> None:
    workflow_store.save_many(
        session_id,
        "requirements",
        output.get("requirements", []),
        "requirement_id",
        replace_all=True,
    )
    analyzed = output.get("analyzed_requirements", [])
    workflow_store.save_many(
        session_id,
        "parsed_requirements",
        analyzed or output.get("requirements", []),
        "requirement_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "analyzed_requirements",
        analyzed,
        "requirement_id",
        replace_all=True,
    )
    _save_prompt_evidence(session_id, output, "requirements", STAGE_PARSE)


def _save_risk(session_id: str, output: dict[str, Any]) -> None:
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
    _save_prompt_evidence(session_id, output, "risk_analysis", STAGE_RISK)


def _save_coverage(session_id: str, output: dict[str, Any]) -> None:
    workflow_store.save_many(
        session_id,
        "coverage_goals",
        output.get("coverage_goals", []),
        "coverage_goal_id",
        replace_all=True,
    )
    _save_prompt_evidence(session_id, output, "coverage_goals", STAGE_COVERAGE)


def _save_strategy(session_id: str, output: dict[str, Any]) -> None:
    workflow_store.save_many(
        session_id,
        "coverage_items",
        output.get("coverage_items", []),
        "coverage_item_id",
        replace_all=True,
    )
    _save_prompt_evidence(session_id, output, "coverage_items", STAGE_STRATEGY)


def _save_generate(session_id: str, output: dict[str, Any]) -> None:
    workflow_store.save_many(
        session_id,
        "test_design_specs",
        output.get("test_design_specs", []),
        "spec_id",
        replace_all=True,
    )
    test_cases = output.get("test_cases", [])
    workflow_store.save_many(session_id, "test_cases", test_cases, "test_id")
    _save_prompt_evidence(session_id, output, "test_cases", STAGE_GENERATE)


def _save_fsm(session_id: str, output: dict[str, Any]) -> None:
    fsm = output.get("fsm") or {}
    workflow_store.save_object(session_id, "fsm", fsm)
    test_cases = output.get("test_cases", [])
    workflow_store.save_many(session_id, "test_cases", test_cases, "test_id")
    _save_prompt_evidence(session_id, output, "fsm", STAGE_FSM)


def _save_oracle(session_id: str, output: dict[str, Any]) -> None:
    oracle_results = output.get("oracle_results", [])
    workflow_store.save_many(
        session_id,
        "oracle_results",
        oracle_results,
        "test_id",
        replace_all=True,
    )
    _save_prompt_evidence(session_id, output, "oracle_results", STAGE_ORACLE)


def _save_prompt_evidence(
    session_id: str,
    output: dict[str, Any],
    target_id: str,
    stage: str,
) -> None:
    evidence = prompt_records_to_evidence(
        session_id=session_id,
        records=output.get("prompts_used"),
        target_id=target_id,
        output_data=stage_output_summary(stage, output),
        note=f"Background pipeline stage {stage} prompt evidence.",
    )
    workflow_store.save_many(session_id, "prompt_evidence", evidence, "evidence_id")
