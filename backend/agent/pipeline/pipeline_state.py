from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.agent_context import AgentContext


@dataclass
class PipelineState:
    """Pipeline 运行时状态，用于记录当前步骤和错误。"""

    context: AgentContext
    current_step: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
