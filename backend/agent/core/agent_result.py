from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentResult:
    """单个 Agent 步骤的统一返回结构。"""

    success: bool
    data: dict[str, Any]
    error: str | None = None
