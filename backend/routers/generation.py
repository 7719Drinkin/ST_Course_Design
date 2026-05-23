"""RAG + DeepSeek 测试生成接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.generation import (
    GenerateTestCasesRequest,
    GenerateTestCasesResponse,
    GenerateTestPointsRequest,
    GenerateTestPointsResponse,
)
from backend.services.deepseek_service import DeepSeekServiceError
from backend.services.test_generation_service import (
    TestGenerationError,
    generate_test_cases,
    generate_test_points,
)

router = APIRouter(tags=["generation"])


@router.post("/generate_test_points", response_model=GenerateTestPointsResponse)
def generate_points(request: GenerateTestPointsRequest) -> GenerateTestPointsResponse:
    """基于需求和 RAG 上下文生成测试点。"""
    try:
        return generate_test_points(requirement=request.requirement, top_k=request.top_k)
    except DeepSeekServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except TestGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/generate_test_cases", response_model=GenerateTestCasesResponse)
def generate_cases(request: GenerateTestCasesRequest) -> GenerateTestCasesResponse:
    """基于需求和 RAG 上下文生成测试用例。"""
    try:
        return generate_test_cases(requirement=request.requirement, top_k=request.top_k)
    except DeepSeekServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except TestGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
