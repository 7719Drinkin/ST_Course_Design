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


# RequirementParseAgent 产物：拆分后的原子需求
class ParsedRequirement(FlexibleModel):
    requirement_id: str           # REQ-AUT-*
    module: str = ""              # 需求所属业务模块
    raw_text: str = ""            # 原始需求文本片段
    description: str = ""         # 原子需求描述


# RequirementAnalysisAgent 产物：抽取黑盒测试设计所需信息
class AnalyzedRequirement(FlexibleModel):
    requirement_id: str           # 对应 ParsedRequirement
    module: str = ""              # 需求所属业务模块
    description: str = ""         # 需求描述
    input_fields: list[str] = Field(default_factory=list)
    data_ranges: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    expected_action: str = ""


# Pipeline 端点 Prompt 调用记录
class PromptRecord(FlexibleModel):
    prompt_name: str
    target_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    note: str = ""
    created_at: str = ""


# Prompt 调用证据（辅助端点使用）
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
    session_id: str = "SESSION-CURRENT"
    requirement_text: str = ""
    rag_context: str | None = None


# POST /parse 响应体
class ParseResponse(FlexibleModel):
    requirements: list[ParsedRequirement]
    analyzed_requirements: list[AnalyzedRequirement]
    prompts_used: list[PromptRecord] = Field(default_factory=list)
