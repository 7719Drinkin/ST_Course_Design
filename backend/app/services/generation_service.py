"""Test case generation gateway service."""

from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.analysis import CoverageItemDto
from backend.app.models.analysis import CoverageItemEntity
from backend.app.models.common import Technique
from backend.app.models.test_design import TestCaseEntity
from backend.app.services.coverage_service import coverage_service
from backend.app.services.risk_service import risk_service
from backend.app.repositories.sample_repository import get_sample_by_id

STANDARD_REFS = {
    "EP": "ISO/IEC/IEEE 29119-4 equivalence partitioning",
    "BVA": "ISO/IEC/IEEE 29119-4 boundary value analysis",
    "DT": "ISO/IEC/IEEE 29119-4 decision table testing",
    "FSM": "ISO/IEC/IEEE 29119-4 state transition testing",
}


def _to_entity(item: CoverageItemDto) -> CoverageItemEntity:
    return CoverageItemEntity(
        coverage_item_id=item.coverage_item_id,
        requirement_id=item.requirement_id,
        description=item.description,
        techniques=item.techniques or ["EP"],
        strategy_rationale=item.strategy_rationale,
        designer_added=item.designer_added,
    )


def _requirement_number(requirement_id: str) -> str:
    match = re.search(r"(\d+)$", requirement_id)
    return match.group(1) if match else requirement_id.replace("REQ-", "")


def _sample_input_value(field: str) -> Any:
    if field.endswith(".id") or field == "id" or field == "recordId":
        return 1
    if field == "availableCopies":
        return 1
    if "date" in field.lower():
        return "2026-05-23"
    return f"valid_{field.replace('.', '_')}"


def _infer_step(raw_requirement: str, input_fields: list[str]) -> str:
    match = re.search(r"\b(GET|POST|PUT|DELETE)\s+(/[A-Za-z0-9_/{}/-]+)", raw_requirement)
    if not match:
        return "Exercise the AUT API according to the requirement"
    payload_hint = f" with {', '.join(input_fields)}" if input_fields else ""
    return f"{match.group(1)} {match.group(2)}{payload_hint}"


class GenerationService:
    def generate(
        self,
        requirement_ids: list[str] | None = None,
        coverage_items: list[CoverageItemDto] | None = None,
    ) -> list[TestCaseEntity]:
        coverage = (
            [_to_entity(item) for item in coverage_items]
            if coverage_items
            else coverage_service.build_items(requirement_ids)
        )
        risk_by_req = {risk.requirement_id: risk.level for risk in risk_service.analyze(requirement_ids)}
        cases: list[TestCaseEntity] = []
        counters: dict[str, int] = {}
        for item in coverage:
            sample = get_sample_by_id(item.requirement_id)
            input_fields = sample.input_fields if sample else []
            preconditions = sample.conditions if sample and sample.conditions else ["Requirement preconditions hold"]
            input_data = {field: _sample_input_value(field) for field in input_fields}
            raw_requirement = sample.raw_requirement if sample else item.description
            for technique in item.techniques:
                counters[item.requirement_id] = counters.get(item.requirement_id, 0) + 1
                index = counters[item.requirement_id]
                title_base = sample.title if sample and sample.title else item.description
                # TODO(Agent): Replace this deterministic case factory with Agent-driven generation.
                cases.append(
                    TestCaseEntity(
                        test_id=f"TC-AUT-{_requirement_number(item.requirement_id)}-{index:03d}",
                        requirement_id=item.requirement_id,
                        coverage_item_id=item.coverage_item_id,
                        technique=technique,
                        title=f"{title_base} [{technique}]",
                        preconditions=preconditions,
                        input_data=input_data,
                        test_steps=[_infer_step(raw_requirement, input_fields)],
                        expected_result=(sample.expected_action if sample else item.description),
                        risk_level=risk_by_req.get(item.requirement_id, "Medium"),
                        standard_ref=STANDARD_REFS.get(technique, "ISO/IEC/IEEE 29119-4"),
                        status="Draft",
                    )
                )
        return cases


generation_service = GenerationService()

