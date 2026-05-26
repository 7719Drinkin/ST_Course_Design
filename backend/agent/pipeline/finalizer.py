from __future__ import annotations

from ..core.models import (
    FullPipelineResult,
    GenerateResult,
    CoverageResult,
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
) -> FullPipelineResult:
    """只负责组装完整结果，不做 ID 改写和质量门禁。"""

    return FullPipelineResult(
        requirements=parse_result.requirements,
        analyzed_requirements=parse_result.analyzed_requirements,
        risk_analysis=risk_result.risk_analysis,
        coverage_goals=coverage_result.coverage_goals,
        coverage_items=strategy_result.coverage_items,
        test_design_specs=generate_result.test_design_specs,
        test_cases=generate_result.test_cases,
        # prompts_used 分阶段收集，这里按真实执行顺序拼接，方便排查某阶段 Prompt。
        prompts_used=[
            *parse_result.prompts_used,
            *risk_result.prompts_used,
            *coverage_result.prompts_used,
            *strategy_result.prompts_used,
            *generate_result.prompts_used,
        ],
    )


def finalize_pipeline_result(
    parse_result: ParseResult,
    risk_result: RiskResult,
    coverage_result: CoverageResult,
    strategy_result: StrategyResult,
    generate_result: GenerateResult,
) -> FullPipelineResult:
    """组装最终结果，并执行统一收尾校验。"""

    result = build_full_pipeline_result(
        parse_result,
        risk_result,
        coverage_result,
        strategy_result,
        generate_result,
    )

    try:
        # LLM 可能生成临时 ID。先规范上游 ID，再用映射同步下游引用，避免断链。
        normalize_all_ids(result)
        # traceability 负责更细的链路一致性，如重复 ID、同一 requirement 链是否一致。
        check_traceability(result)
        # final gate 负责最终交付门槛，如产物非空和用例优先级是否回到风险分析。
        run_final_quality_gate(result)
    except Exception as exc:
        raise StageExecutionError(StageName.FINAL_VALIDATION, str(exc), result) from exc

    return result
