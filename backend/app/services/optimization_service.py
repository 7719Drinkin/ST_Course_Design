"""Suite optimization service."""

from __future__ import annotations

from backend.app.models.common import OptimizeMode
from backend.app.models.test_design import OptimizeResultEntity


class OptimizationService:
    def optimize(self, mode: OptimizeMode, test_ids: list[str] | None = None) -> OptimizeResultEntity:
        ids = test_ids or []
        # TODO(Agent): Connect the real suite optimization module.
        return OptimizeResultEntity(
            before_count=len(ids),
            after_count=len(ids),
            mode=mode,
            reduction_rate=0,
            removed_test_ids=[],
        )


optimization_service = OptimizationService()
