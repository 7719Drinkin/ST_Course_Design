"""RAG 测试生成接口 schema。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Priority = Literal["High", "Medium", "Low"]
TestPointType = Literal[
    "Boundary",
    "Equivalence",
    "StateTransition",
    "Exception",
    "Functional",
    "Security",
    "Performance",
    "Other",
]
ContextQuality = Literal["high", "medium", "low"]


class GenerateTestPointsRequest(BaseModel):
    """测试点生成请求。"""

    requirement: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("requirement")
    @classmethod
    def requirement_not_blank(cls, value: str) -> str:
        """禁止空白需求进入生成流程。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("requirement 不能为空")
        return cleaned


class GenerateTestCasesRequest(BaseModel):
    """测试用例生成请求。"""

    requirement: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("requirement")
    @classmethod
    def requirement_not_blank(cls, value: str) -> str:
        """禁止空白需求进入生成流程。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("requirement 不能为空")
        return cleaned


class InferredText(BaseModel):
    """带 inferred 标记的文本项。"""

    content: str
    inferred: bool = False


class TestObjective(InferredText):
    """测试目标。"""


class RiskItem(InferredText):
    """风险项。"""


class ScenarioItem(InferredText):
    """测试场景项。"""


class SourceRef(BaseModel):
    """后端从 retrieval metadata 中提取的来源引用。"""

    source: str = ""
    section: str = ""
    chunk_id: str = ""


class TestPoint(BaseModel):
    """结构化测试点。"""

    id: str = Field(..., pattern=r"^TP\d{3}$")
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    type: TestPointType = "Other"
    priority: Priority = "Medium"
    inferred: bool = False


class TestCase(BaseModel):
    """结构化测试用例。"""

    case_id: str = Field(..., pattern=r"^TC\d{3}$")
    title: str = Field(..., min_length=1)
    precondition: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str = Field(..., min_length=1)
    priority: Priority = "Medium"
    type: TestPointType = "Other"
    related_test_point: str
    inferred: bool = False


class GenerateTestPointsResponse(BaseModel):
    """测试点生成响应。"""

    requirement: str
    context_quality: ContextQuality = "low"
    test_objectives: list[TestObjective] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    test_points: list[TestPoint] = Field(default_factory=list)
    boundary_scenarios: list[ScenarioItem] = Field(default_factory=list)
    exception_scenarios: list[ScenarioItem] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)


class GenerateTestCasesResponse(BaseModel):
    """测试用例生成响应。"""

    requirement: str
    test_cases: list[TestCase] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
