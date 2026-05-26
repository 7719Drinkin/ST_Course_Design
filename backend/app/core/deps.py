"""FastAPI dependency injection — single source for all Depends() callables."""

from ..modules.generation.service import GenerationService
from ..modules.requirements.service import RequirementService


def get_generation_service() -> GenerationService:
    return GenerationService()


def get_requirement_service() -> RequirementService:
    return RequirementService()
