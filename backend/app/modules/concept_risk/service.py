"""Step 2 business logic: concept identification and risk scoring."""

from __future__ import annotations

import re

from fastapi import HTTPException

from ..util import to_dicts
from ..store import workflow_store
from .schemas import ConceptsRequest, ConceptsResponse, RiskRequest, RiskResponse


class ConceptRiskService:
    def extract_concepts(self, request: ConceptsRequest) -> ConceptsResponse:
        """Identify business concepts from requirements.

        TODO: 接入 B Agent 的 concept extraction Prompt。
              输入：requirements, parsed_requirements
              输出：list[Concept]（含 concept_id, name, type, evidence）
        """
        workflow_store.save_many(request.session_id, "concepts", [], "concept_id")
        return ConceptsResponse(
            session_id=request.session_id,
            concepts=[],
            prompt_evidence=[],
        )

    def score_risk(self, request: RiskRequest) -> RiskResponse:
        """Risk scoring for requirements or coverage items.

        TODO: 接入 B Agent 的 risk scoring Prompt + 风险矩阵。
              输入：targets（每条含 target_id, target_type, text）
              输出：list[RiskResult]（含 impact, likelihood, risk_score,
                    risk_level, test_priority, reason, evidence）
              校验规则：target_id 必须以 REQ-AUT-/FR-AUT-/COV-AUT- 开头。
        """
        targets = to_dicts(request.targets) if request.targets else []
        for target in targets:
            target_id = str(target.get("target_id", ""))
            if not re.match(r"^(REQ-AUT|FR-AUT|COV-AUT)-", target_id):
                raise HTTPException(
                    status_code=422,
                    detail=f"target_id must start with REQ-AUT-, FR-AUT-, or COV-AUT-: {target_id}",
                )

        workflow_store.save_many(request.session_id, "risk_results", [], "target_id")
        return RiskResponse(
            session_id=request.session_id,
            risk_results=[],
            prompt_evidence=[],
        )
