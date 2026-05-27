from __future__ import annotations

from typing import Any


class StageExecutionError(Exception):
    """阶段执行失败的统一异常，runner 会用它保留真实 failed_step。"""

    def __init__(self, stage: str, error: str, partial_result: Any | None = None) -> None:
        super().__init__(error)
        self.stage = stage
        self.error = error
        self.partial_result = partial_result
