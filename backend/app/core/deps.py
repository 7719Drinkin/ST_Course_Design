"""FastAPI dependency injection — single source for all Depends() callables."""

from ..modules.requirements.service import RequirementService


def get_requirement_service() -> RequirementService:
    return RequirementService()
