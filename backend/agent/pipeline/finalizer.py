from __future__ import annotations

from ..core.models import (
    CoverageResult,
    FullPipelineResult,
    FsmGenerationResult,
    GenerateResult,
    MergedTestCase,
    OracleGenerationResult,
    ParseResult,
    RiskResult,
    StrategyResult,
)
from ..tools.validation.final_quality_gate import run_final_quality_gate
from ..tools.validation.id_normalizer import normalize_all_ids
from ..tools.validation.traceability_checker import check_traceability
from .errors import StageExecutionError
from .stages import StageName


def build_full_pipeline_result(
    parse_result: ParseResult,
    risk_result: RiskResult,
    coverage_result: CoverageResult,
    strategy_result: StrategyResult,
    generate_result: GenerateResult,
    fsm_result: FsmGenerationResult,
    oracle_result: OracleGenerationResult,
) -> FullPipelineResult:
    """Only assemble artifacts. ID rewrite and quality gates happen in finalizer."""

    return FullPipelineResult(
        requirements=parse_result.requirements,
        analyzed_requirements=parse_result.analyzed_requirements,
        risk_analysis=risk_result.risk_analysis,
        coverage_goals=coverage_result.coverage_goals,
        coverage_items=strategy_result.coverage_items,
        test_design_specs=generate_result.test_design_specs,
        test_cases=generate_result.test_cases,
        fsm=fsm_result.fsm,
        fsm_test_cases=fsm_result.test_cases,
        all_test_cases=_merge_test_cases(generate_result.test_cases, fsm_result.test_cases),
        oracle_results=oracle_result.oracle_results,
        prompts_used=[
            *parse_result.prompts_used,
            *risk_result.prompts_used,
            *coverage_result.prompts_used,
            *strategy_result.prompts_used,
            *generate_result.prompts_used,
            *fsm_result.prompts_used,
            *oracle_result.prompts_used,
        ],
    )


def finalize_pipeline_result(
    parse_result: ParseResult,
    risk_result: RiskResult,
    coverage_result: CoverageResult,
    strategy_result: StrategyResult,
    generate_result: GenerateResult,
    fsm_result: FsmGenerationResult,
    oracle_result: OracleGenerationResult,
) -> FullPipelineResult:
    """Assemble the final result and run shared post checks."""

    result = build_full_pipeline_result(
        parse_result,
        risk_result,
        coverage_result,
        strategy_result,
        generate_result,
        fsm_result,
        oracle_result,
    )

    try:
        # Keep FR5 outputs aligned after FR3 IDs are normalized in the final pass.
        original_fr3_test_ids = [item.test_id for item in result.test_cases]
        normalize_all_ids(result)
        normalized_fr3_test_ids = [item.test_id for item in result.test_cases]
        result.all_test_cases = _merge_test_cases(result.test_cases, result.fsm_test_cases)
        _align_oracle_results(result, original_fr3_test_ids, normalized_fr3_test_ids)
        check_traceability(result)
        run_final_quality_gate(result)
    except Exception as exc:
        raise StageExecutionError(StageName.FINAL_VALIDATION, str(exc), result) from exc

    return result


def _merge_test_cases(fr3_cases: list, fr4_cases: list) -> list[MergedTestCase]:
    merged: list[MergedTestCase] = []

    for test_case in fr3_cases:
        payload = test_case.model_dump(mode="json")
        merged.append(
            MergedTestCase(
                source="FR3",
                test_id=str(payload.get("test_id", "")),
                requirement_id=str(payload.get("requirement_id", "")),
                technique=str(payload.get("technique", "")),
                test_case=payload,
            )
        )

    for test_case in fr4_cases:
        payload = test_case.model_dump(mode="json")
        merged.append(
            MergedTestCase(
                source="FR4",
                test_id=str(payload.get("test_id", "")),
                requirement_id=str(payload.get("requirement_id", "")),
                technique=str(payload.get("technique", "")),
                test_case=payload,
            )
        )

    return merged


def _align_oracle_results(
    result: FullPipelineResult,
    original_fr3_test_ids: list[str],
    normalized_fr3_test_ids: list[str],
) -> None:
    if not result.oracle_results:
        return

    merged_test_ids = [item.test_id for item in result.all_test_cases]
    if len(merged_test_ids) == len(result.oracle_results):
        for oracle_item, test_id in zip(result.oracle_results, merged_test_ids):
            oracle_item.test_id = test_id
        return

    fr3_id_map = {
        original_id: normalized_id
        for original_id, normalized_id in zip(original_fr3_test_ids, normalized_fr3_test_ids)
    }
    for oracle_item in result.oracle_results:
        if oracle_item.test_id in fr3_id_map:
            oracle_item.test_id = fr3_id_map[oracle_item.test_id]
