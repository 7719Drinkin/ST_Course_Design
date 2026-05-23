"""Oracle review service."""

from __future__ import annotations

from backend.app.models.test_design import OracleResultEntity


class OracleService:
    def evaluate(self, test_ids: list[str] | None = None) -> list[OracleResultEntity]:
        # TODO(RAG): Replace stub verdicts with RAG-backed oracle validation.
        return [
            OracleResultEntity(
                test_id=test_id,
                llm_verdict="Pass",
                rule_verdict="Pass",
                confidence=0.9,
                needs_review=False,
            )
            for test_id in (test_ids or [])
        ]


oracle_service = OracleService()

