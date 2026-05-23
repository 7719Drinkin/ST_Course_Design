"""Oracle review service."""

from __future__ import annotations

from backend.app.models.test_design import OracleResultEntity


class OracleService:
    def evaluate(self, test_ids: list[str] | None = None) -> list[OracleResultEntity]:
        # TODO(RAG): Connect the real oracle validation module.
        return []


oracle_service = OracleService()
