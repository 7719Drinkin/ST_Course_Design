"""通用 schema。"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """统一错误响应结构。"""

    detail: str
