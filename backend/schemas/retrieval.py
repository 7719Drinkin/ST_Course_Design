"""RAG 检索接口 schema。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.utils.config import DEFAULT_TOP_K


class RetrieveRequest(BaseModel):
    """检索请求。"""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        """禁止空白 query 进入检索流程。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query 不能为空")
        return cleaned


class RetrievedChunk(BaseModel):
    """单条检索结果。"""

    content: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    """检索响应。"""

    query: str
    results: list[RetrievedChunk] = Field(default_factory=list)
