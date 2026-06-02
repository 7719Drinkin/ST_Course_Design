"""Step 3 business logic: coverage goals and strategy assignment — store-first read, no inline pipeline."""

from __future__ import annotations

from ..store import workflow_store
from .schemas import (
    CoverageRequest,
    CoverageResponse,
    StrategyRequest,
    StrategyResponse,
)


class CoverageStrategyService:

    async def generate_coverage(self, request: CoverageRequest) -> CoverageResponse:
        stored = workflow_store.get_list(request.session_id, "coverage_goals")
        if stored:
            evidence = workflow_store.get_list(request.session_id, "prompt_evidence")
            return CoverageResponse(coverage_goals=stored, prompts_used=evidence)
        return CoverageResponse(coverage_goals=[], prompts_used=[])

    async def assign_strategy(self, request: StrategyRequest) -> StrategyResponse:
        stored = workflow_store.get_list(request.session_id, "coverage_items")
        if stored:
            evidence = workflow_store.get_list(request.session_id, "prompt_evidence")
            return StrategyResponse(coverage_items=stored, prompts_used=evidence)
        return StrategyResponse(coverage_items=[], prompts_used=[])
