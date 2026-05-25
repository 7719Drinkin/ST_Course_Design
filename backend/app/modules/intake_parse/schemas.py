"""Step 1 schemas — 需求摄入与结构化解析相关的请求/响应和领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# 基础模型，允许额外字段透传，前端兼容性保障
class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# POST /ingest 请求体：提交需求文本
class IngestRequest(BaseModel):
    content: str = ""


# 通用 API 错误响应
class ApiError(FlexibleModel):
    code: str
    message: str
    target_id: str | None = None
    detail: Any | None = None


# 原始需求条目
class Requirement(FlexibleModel):
    requirement_id: str | None = None
    text: str | None = None
    raw_text: str | None = None
    description: str | None = None
    title: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# 结构化解析后的需求（Agent B 输出）
class ParsedRequirement(FlexibleModel):
    requirement_id: str
    input_fields: list[str] = Field(default_factory=list)
    data_ranges: list[Any] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    expected_action: str = ""
    confidence: float = 0.0
    missing_fields: list[str] = Field(default_factory=list)


# Prompt 调用证据（Agent 或占位逻辑生成）
class PromptEvidence(FlexibleModel):
    evidence_id: str
    session_id: str
    prompt_name: str
    target_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    note: str = ""
    created_at: str


# POST /parse 请求体
class ParseRequest(FlexibleModel):
    session_id: str
    requirement_ids: list[str] | None = None
    requirements: list[Requirement] | None = None
    include_prompt_evidence: bool = True


# POST /parse 响应体
class ParseResponse(FlexibleModel):
    session_id: str
    parsed_requirements: list[ParsedRequirement]
    prompt_evidence: list[PromptEvidence] = Field(default_factory=list)
    errors: list[ApiError] = Field(default_factory=list)
