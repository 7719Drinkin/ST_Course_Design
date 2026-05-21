"""AutoTestDesign 后端数据模型。

课程项目阶段先把 Pydantic model 集中放在一个文件，便于前端、测试和后端成员快速查阅。
这些模型围绕测试设计工具本身，不描述 AUT 的业务实体。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Status = Literal["ai_generated", "human_revised", "human_added"]
Technique = Literal["EP", "BVA", "DT", "FSM", "ORACLE"]


class Requirement(BaseModel):
    """输入到测试设计工具的需求条目。"""

    requirement_id: str
    text: str
    source: str = "manual_input"
    module: str = "general"


class ParsedRequirement(BaseModel):
    """结构化需求解析结果，供风险、覆盖项和用例生成追溯使用。"""

    requirement_id: str
    actor: str = "API client"
    action: str = ""
    object: str = ""
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class RiskScore(BaseModel):
    """Impact × Likelihood 风险评分结果。"""

    requirement_id: str
    impact: int
    likelihood: int
    risk_level: str
    rationale: str


class CoverageItem(BaseModel):
    """覆盖项是需求和测试用例之间的追溯桥梁。"""

    coverage_item_id: str
    requirement_id: str
    technique: Technique
    description: str
    status: Status = "ai_generated"
    original_description: str = ""


class TestCase(BaseModel):
    """生成后的测试用例，保留 coverage_item_id 方便 Interactive Review 回溯。"""

    test_id: str
    requirement_id: str
    coverage_item_id: str
    technique: Technique
    input_values: dict[str, Any] = Field(default_factory=dict)
    expected_result: str
    standard_ref: str = "ISO/IEC/IEEE 29119-4"
    risk_level: str = "Medium"
    status: Status = "ai_generated"
    revision_count: int = 0


class RevisionRecord(BaseModel):
    """人机审查中的单次人工修改记录。"""

    revision_id: str
    item_id: str
    item_type: str
    field_changed: str
    original_value: Any
    revised_value: Any
    revision_reason: str
    timestamp: str


class DesignSession(BaseModel):
    """一次测试设计会话的轻量快照。

    prompts_used 用于后续保存 RAG/LLM prompt，revision_count 用于展示人工参与程度。
    """

    session_id: str
    created_at: str
    requirement_input: list[Requirement] = Field(default_factory=list)
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    prompts_used: list[str] = Field(default_factory=list)
    revision_count: int = 0


class IngestRequest(BaseModel):
    """需求输入请求；content 为空时加载样例需求。"""

    source_type: str = "text"
    content: Any = ""


class ParseRequest(BaseModel):
    """单条需求解析请求。"""

    requirement_id: str
    text: str = ""


class RequirementIdsRequest(BaseModel):
    """按需求编号筛选的通用请求。"""

    requirement_ids: list[str] = Field(default_factory=list)


class CoverageGenerateRequest(BaseModel):
    """覆盖项生成请求。"""

    parsed_requirements: list[ParsedRequirement] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class TestCaseGenerateRequest(BaseModel):
    """测试用例生成请求。"""

    coverage_items: list[CoverageItem] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class ReviseRequest(BaseModel):
    """人工修改请求。"""

    item_id: str
    item_type: str
    field_changed: str
    original_value: Any
    revised_value: Any
    revision_reason: str = ""


class RegenerateRequest(BaseModel):
    """根据人工修改触发再生成的请求。"""

    revision_id: str = ""
    item_id: str = ""
    mode: str = "incremental"


class ExportRequest(BaseModel):
    """导出请求，允许前端把当前工作区数据一次性传入。"""

    requirements: list[Requirement] = Field(default_factory=list)
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    revisions: list[RevisionRecord] = Field(default_factory=list)
