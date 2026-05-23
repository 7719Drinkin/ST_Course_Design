"""导出接口 schema。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    """导出请求。"""

    format: Literal["markdown"] = "markdown"
    data: dict[str, Any] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    """导出响应。"""

    format: Literal["markdown"]
    content: str
