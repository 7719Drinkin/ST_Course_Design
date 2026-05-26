"""Test generation routes (/generate)."""

from fastapi import APIRouter, Depends

from ...core.deps import get_generation_service
from .schemas import GenerateRequest, GenerateResponse
from .service import GenerationService


router = APIRouter(tags=["generation"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    service: GenerationService = Depends(get_generation_service),
) -> GenerateResponse:
    return await service.generate_test_cases(request)
