from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Agent 链路共享上下文，承载各阶段结构化中间结果。"""

    requirement_text: str | None = None
    requirements: list[dict[str, Any]] = field(default_factory=list)
    analyzed_requirements: list[dict[str, Any]] = field(default_factory=list)
    risk_analysis: list[dict[str, Any]] = field(default_factory=list)
    coverage_goals: list[dict[str, Any]] = field(default_factory=list)
    coverage_items: list[dict[str, Any]] = field(default_factory=list)
    test_design_specs: list[dict[str, Any]] = field(default_factory=list)
    test_cases: list[dict[str, Any]] = field(default_factory=list)
    rag_context: str | None = None
    prompts_used: list[dict[str, str]] = field(default_factory=list)
