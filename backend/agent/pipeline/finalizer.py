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
from ..tools.validation.id_gate import require_pipeline_id_formats
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
        result.all_test_cases = _merge_test_cases(result.test_cases, result.fsm_test_cases)
        require_pipeline_id_formats(result)
        _check_complete_pipeline_sets(result)
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

def _check_complete_pipeline_sets(result: FullPipelineResult) -> None:
    analyzed_requirement_ids = {item.requirement_id for item in result.analyzed_requirements}
    risk_requirement_ids = {item.requirement_id for item in result.risk_analysis}
    if analyzed_requirement_ids != risk_requirement_ids:
        missing = sorted(analyzed_requirement_ids - risk_requirement_ids)
        extra = sorted(risk_requirement_ids - analyzed_requirement_ids)
        raise ValueError(
            f"risk_analysis must exactly cover analyzed_requirements. "
            f"missing={missing or []}, extra={extra or []}"
        )

    coverage_ids = {item.coverage_item_id for item in result.coverage_items}
    spec_coverage_ids = {item.coverage_item_id for item in result.test_design_specs}
    test_coverage_ids = {item.coverage_item_id for item in result.test_cases}
    missing_specs = sorted(coverage_ids - spec_coverage_ids)
    missing_tests = sorted(coverage_ids - test_coverage_ids)
    if missing_specs:
        raise ValueError("coverage_items without test_design_specs: " + ", ".join(missing_specs))
    if missing_tests:
        raise ValueError("coverage_items without test_cases: " + ", ".join(missing_tests))

    _require_unique([item.test_id for item in result.test_cases], "test_cases.test_id")
    _require_unique([item.test_id for item in result.fsm_test_cases], "fsm_test_cases.test_id")
    merged_test_ids = [item.test_id for item in result.all_test_cases]
    _require_unique(merged_test_ids, "all_test_cases.test_id")

    oracle_ids = [item.test_id for item in result.oracle_results]
    _require_unique(oracle_ids, "oracle_results.test_id")
    if set(oracle_ids) != set(merged_test_ids):
        missing = sorted(set(merged_test_ids) - set(oracle_ids))
        extra = sorted(set(oracle_ids) - set(merged_test_ids))
        raise ValueError(
            f"oracle_results must match final test cases. "
            f"missing={missing or []}, extra={extra or []}"
        )


def _require_unique(values: list[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"{label} contains duplicate IDs: {sorted(duplicates)}")
