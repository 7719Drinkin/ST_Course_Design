"""Suite optimization service."""

from __future__ import annotations

from backend.app.models.common import OptimizeMode
from backend.app.models.test_design import OptimizeResultEntity


class OptimizationService:
    def optimize(self, mode: OptimizeMode, test_ids: list[str] | None = None) -> OptimizeResultEntity:
        ids = test_ids or []
        before = len(ids)
        # TODO(Agent): Replace deterministic pruning with Agent algorithm optimization.
        removed = ids[3::4] if mode == "risk_priority" and before > 3 else []
        after = before - len(removed)
        reduction_rate = round((len(removed) / before) * 100) if before else 0
        return OptimizeResultEntity(
            before_count=before,
            after_count=after,
            mode=mode,
            reduction_rate=reduction_rate,
            removed_test_ids=removed,
        )


optimization_service = OptimizationService()

