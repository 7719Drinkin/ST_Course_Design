"""Background pipeline runner.

The visible /parse request owns the only parse pass.  This module continues the
same AgentPipeline from that ParseResult so frontend requirements and downstream
risk/coverage/test artifacts share one requirement-id source.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agent import AgentPipeline
from agent.core.models import ParseResult
from agent.pipeline.finalizer import finalize_pipeline_result

from .store import workflow_store
from .util import (
    STAGE_COVERAGE,
    STAGE_FSM,
    STAGE_GENERATE,
    STAGE_ORACLE,
    STAGE_RISK,
    STAGE_STRATEGY,
    dedupe_oracle_results,
    fsm_coverage_items_from_test_cases,
    merge_by_id,
    prompt_records_to_evidence,
    risk_analysis_to_risk_results,
    stage_output_summary,
    strategies_from_coverage_items,
)

logger = logging.getLogger(__name__)


async def _background_pipeline_after_parse(
    session_id: str,
    pipeline: AgentPipeline,
    parse_result: ParseResult,
    rag_context: str | None,
) -> None:
    """Run risk and later stages using the exact parse_result returned to the frontend."""

    try:
        risk_result = await pipeline.analyze_risk(parse_result.analyzed_requirements, rag_context)
        _require_exact_requirement_ids(
            stage=STAGE_RISK,
            expected=parse_result.analyzed_requirements,
            actual=risk_result.risk_analysis,
        )
        _save_risk(session_id, risk_result.model_dump(mode="json"))

        coverage_result = await pipeline.identify_coverage(
            parse_result.analyzed_requirements,
            risk_result.risk_analysis,
            rag_context,
        )
        _require_known_requirement_ids(
            stage=STAGE_COVERAGE,
            valid=parse_result.analyzed_requirements,
            items=coverage_result.coverage_goals,
        )
        _save_coverage(session_id, coverage_result.model_dump(mode="json"))

        strategy_result = await pipeline.assign_strategy(
            coverage_result.coverage_goals,
            parse_result.analyzed_requirements,
            risk_result.risk_analysis,
            rag_context,
        )
        _require_known_requirement_ids(
            stage=STAGE_STRATEGY,
            valid=parse_result.analyzed_requirements,
            items=strategy_result.coverage_items,
        )
        _save_strategy(session_id, strategy_result.model_dump(mode="json"))

        fsm_task = asyncio.create_task(
            pipeline.generate_fsm(
                requirements=parse_result.requirements,
                parsed_requirements=parse_result.analyzed_requirements,
                rag_context=rag_context,
            )
        )
        generate_result = await pipeline.generate_tests(
            strategy_result.coverage_items,
            risk_result.risk_analysis,
            rag_context,
        )
        _require_known_requirement_ids(
            stage=STAGE_GENERATE,
            valid=parse_result.analyzed_requirements,
            items=generate_result.test_design_specs,
        )
        _require_known_requirement_ids(
            stage=STAGE_GENERATE,
            valid=parse_result.analyzed_requirements,
            items=generate_result.test_cases,
        )
        _save_generate(session_id, generate_result.model_dump(mode="json"))

        fsm_result = await fsm_task
        _require_known_requirement_ids(
            stage=STAGE_FSM,
            valid=parse_result.analyzed_requirements,
            items=fsm_result.test_cases,
        )
        _save_fsm(session_id, fsm_result.model_dump(mode="json"))

        oracle_result = await pipeline.generate_oracles(
            _test_cases_for_oracle(generate_result.test_cases, fsm_result.test_cases),
            requirements=parse_result.analyzed_requirements,
            rag_context=rag_context,
        )
        _save_oracle(session_id, oracle_result.model_dump(mode="json"))

        final_result = finalize_pipeline_result(
            parse_result,
            risk_result,
            coverage_result,
            strategy_result,
            generate_result,
            fsm_result,
            oracle_result,
        )
        _save_final_output(session_id, final_result.model_dump(mode="json"))
        logger.info("Background pipeline completed for session %s", session_id)
    except Exception:
        logger.exception("Background pipeline failed for session %s", session_id)


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
    coverage_items = output.get("coverage_items", [])
    workflow_store.save_many(
        session_id,
        "coverage_items",
        coverage_items,
        "coverage_item_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "strategies",
        strategies_from_coverage_items(coverage_items),
        "strategy_id",
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
    workflow_store.save_many(
        session_id,
        "test_cases",
        output.get("test_cases", []),
        "test_id",
        replace_all=True,
    )
    _save_prompt_evidence(session_id, output, "test_cases", STAGE_GENERATE)


def _save_fsm(session_id: str, output: dict[str, Any]) -> None:
    fsm = output.get("fsm") or {}
    workflow_store.save_object(session_id, "fsm", fsm)
    test_cases = output.get("test_cases", [])
    workflow_store.save_many(session_id, "fsm_test_cases", test_cases, "test_id", replace_all=True)
    fsm_coverage_items = fsm_coverage_items_from_test_cases(test_cases)
    if fsm_coverage_items:
        workflow_store.save_many(session_id, "coverage_items", fsm_coverage_items, "coverage_item_id")
        all_coverage = workflow_store.get_list(session_id, "coverage_items")
        workflow_store.save_many(
            session_id,
            "strategies",
            strategies_from_coverage_items(all_coverage),
            "strategy_id",
            replace_all=True,
        )
    _save_prompt_evidence(session_id, output, "fsm", STAGE_FSM)


def _save_oracle(session_id: str, output: dict[str, Any]) -> None:
    oracle_results = dedupe_oracle_results(output.get("oracle_results", []))
    workflow_store.save_many(
        session_id,
        "oracle_results",
        oracle_results,
        "test_id",
        replace_all=True,
    )
    _save_prompt_evidence(session_id, output, "oracle_results", STAGE_ORACLE)


def _save_final_output(session_id: str, output: dict[str, Any]) -> None:
    """Persist the final normalized artifacts after finalizer ID alignment."""

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
        analyzed,
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
    workflow_store.save_many(
        session_id,
        "coverage_goals",
        output.get("coverage_goals", []),
        "coverage_goal_id",
        replace_all=True,
    )

    fsm_test_cases = output.get("fsm_test_cases", [])
    coverage_items = merge_by_id(
        output.get("coverage_items", []),
        fsm_coverage_items_from_test_cases(fsm_test_cases),
        "coverage_item_id",
    )
    workflow_store.save_many(
        session_id,
        "coverage_items",
        coverage_items,
        "coverage_item_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "strategies",
        strategies_from_coverage_items(coverage_items),
        "strategy_id",
        replace_all=True,
    )

    workflow_store.save_many(
        session_id,
        "test_design_specs",
        output.get("test_design_specs", []),
        "spec_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "test_cases",
        output.get("test_cases", []),
        "test_id",
        replace_all=True,
    )
    workflow_store.save_object(session_id, "fsm", output.get("fsm") or {})
    workflow_store.save_many(
        session_id,
        "fsm_test_cases",
        fsm_test_cases,
        "test_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "oracle_results",
        dedupe_oracle_results(output.get("oracle_results", [])),
        "test_id",
        replace_all=True,
    )


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


def _require_exact_requirement_ids(
    *,
    stage: str,
    expected: list[Any],
    actual: list[Any],
) -> None:
    expected_ids = _ids(expected)
    actual_ids = _ids(actual)
    if expected_ids != actual_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise ValueError(
            f"{stage} requirement_id mismatch. "
            f"missing={missing or []}, extra={extra or []}"
        )


def _require_known_requirement_ids(
    *,
    stage: str,
    valid: list[Any],
    items: list[Any],
    field: str = "requirement_id",
) -> None:
    valid_ids = _ids(valid)
    unknown = sorted(
        {
            item_id
            for item in items
            if (item_id := str(_get(item, field) or "")) and item_id not in valid_ids
        }
    )
    if unknown:
        raise ValueError(f"{stage} produced unknown requirement_id values: {unknown}")


def _ids(items: list[Any]) -> set[str]:
    return {str(_get(item, "requirement_id")) for item in items if _get(item, "requirement_id")}


def _get(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def _test_cases_for_oracle(fr3_cases: list[Any], fsm_cases: list[Any]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for item in fr3_cases:
        payload = _model_dump(item)
        payload["test_source"] = "FR3"
        merged.append(payload)
    for item in fsm_cases:
        payload = _model_dump(item)
        payload["test_source"] = "FR4"
        merged.append(payload)
    return merged


def _model_dump(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if hasattr(item, "to_dict"):
        return item.to_dict()
    raise TypeError(f"Unsupported test case item type: {type(item)!r}")
