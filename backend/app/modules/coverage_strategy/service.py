"""Step 3 business logic: coverage items and strategy assignment."""

from __future__ import annotations

from ..store import workflow_store
from .schemas import (
    CoverageRequest,
    CoverageResponse,
    StrategyRequest,
    StrategyResponse,
)


class CoverageStrategyService:
    def generate_coverage(self, request: CoverageRequest) -> CoverageResponse:
        """Generate and normalise coverage items.

        TODO: 接入 B Agent 生成候选覆盖项，再接入 E Agent 做去重、编号和结构化。
              输入：parsed_requirements, concepts, risk_results
              输出：list[CoverageItem]（含 coverage_item_id, requirement_id,
                    description, technique, strategy, status, source）
        """
        workflow_store.save_many(request.session_id, "coverage_items", [], "coverage_item_id")
        return CoverageResponse(
            session_id=request.session_id,
            coverage_items=[],
            prompt_evidence=[],
        )

    def assign_strategy(self, request: StrategyRequest) -> StrategyResponse:
        """Assign test strategies to coverage items.

        TODO: 接入 B Agent 生成策略建议和标准依据，再接入 E Agent 转换为算法可执行参数。
              输入：coverage_items, risk_results, parsed_requirements
              输出：list[Strategy]（含 strategy_id, coverage_item_id, technique,
                    standard_ref, reason, algorithm_params）
        """
        workflow_store.save_many(request.session_id, "strategies", [], "strategy_id")
        return StrategyResponse(
            session_id=request.session_id,
            strategies=[],
            prompt_evidence=[],
        )
