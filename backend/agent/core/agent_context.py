from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import (
    AnalyzedRequirement,
    CoverageGoal,
    CoverageItem,
    FsmResult,
    FsmTestCaseDraft,
    ParsedRequirement,
    PromptRecord,
    RiskAnalysisItem,
    TestCaseDraft,
    TestDesignSpec,
)


@dataclass
class AgentContext:
    """Agent 链路共享上下文，承载各阶段结构化中间结果。"""

    requirement_text: str | None = None
    requirements: list[ParsedRequirement] = field(default_factory=list)
    analyzed_requirements: list[AnalyzedRequirement] = field(default_factory=list)
    risk_analysis: list[RiskAnalysisItem] = field(default_factory=list)
    coverage_goals: list[CoverageGoal] = field(default_factory=list)
    coverage_items: list[CoverageItem] = field(default_factory=list)
    test_design_specs: list[TestDesignSpec] = field(default_factory=list)
    test_cases: list[TestCaseDraft] = field(default_factory=list)
    fsm_requirements: list[dict[str, Any]] = field(default_factory=list)
    fsm_parsed_requirements: list[dict[str, Any]] = field(default_factory=list)
    fsm_coverage_items: list[dict[str, Any]] = field(default_factory=list)
    state_candidates: list[str] = field(default_factory=list)
    fsm: FsmResult | None = None
    fsm_test_cases: list[FsmTestCaseDraft] = field(default_factory=list)
    rag_context: str | None = None
    prompts_used: list[PromptRecord] = field(default_factory=list)
