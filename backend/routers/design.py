"""测试设计主流程接口。

包含需求输入、解析、风险分析、覆盖项生成和测试用例生成。
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.models import (
    CoverageGenerateRequest,
    CoverageItem,
    IngestRequest,
    ParsedRequirement,
    ParseRequest,
    Requirement,
    RequirementIdsRequest,
    RiskScore,
    TestCase,
    TestCaseGenerateRequest,
)
from backend.services.coverage import build_coverage_items
from backend.services.generation import generate_test_cases
from backend.services.parsing import ingest_requirements, parse_requirement
from backend.services.risk import analyze_risk

router = APIRouter(tags=["design"])


@router.post("/ingest")
def ingest(request: IngestRequest) -> dict[str, list[Requirement] | list[str]]:
    """导入需求；空输入时返回内置 15 条样例。"""
    return ingest_requirements(request.source_type, request.content)


@router.post("/parse", response_model=ParsedRequirement)
def parse(request: ParseRequest) -> ParsedRequirement:
    """解析单条需求。"""
    return parse_requirement(request.requirement_id, request.text)


@router.post("/risk", response_model=list[RiskScore])
def risk(request: RequirementIdsRequest) -> list[RiskScore]:
    """生成风险评分。"""
    return analyze_risk(request.requirement_ids)


@router.post("/coverage", response_model=list[CoverageItem])
def coverage(request: CoverageGenerateRequest) -> list[CoverageItem]:
    """生成覆盖项。"""
    return build_coverage_items(request.parsed_requirements, request.requirement_ids)


@router.post("/generate", response_model=list[TestCase])
def generate(request: TestCaseGenerateRequest) -> list[TestCase]:
    """生成测试用例。"""
    return generate_test_cases(request.coverage_items, request.requirement_ids)
