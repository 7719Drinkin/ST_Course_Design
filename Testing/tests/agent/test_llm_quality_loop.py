from __future__ import annotations

"""LLM repair-loop quality tests for role agents."""

import pytest

from backend.agent.core.agent_context import AgentContext
from backend.agent.core.models import (
    AnalyzedRequirement,
    CoverageItem as CoverageItemModel,
    RiskAnalysisItem,
    TestDesignSpec as DesignSpecModel,
)
from backend.agent.roles.coverage_identification_agent import (
    CoverageIdentificationAgent as CoverageAgentImpl,
)
from backend.agent.roles.test_case_draft_agent import (
    TestCaseDraftAgent as CaseDraftAgentImpl,
)
from backend.agent.roles.test_design_spec_agent import (
    TestDesignSpecAgent as DesignSpecAgentImpl,
)


@pytest.mark.asyncio
async def test_test_design_spec_agent_asks_llm_to_repair_bad_spec_ids():
    client = _RepairingSpecClient()
    agent = DesignSpecAgentImpl(llm_client=client)
    context = AgentContext(
        coverage_items=[
            _coverage("COV-AUT-001-001-EP-001"),
            _coverage("COV-AUT-001-002-EP-001"),
        ],
        risk_analysis=[_risk()],
    )

    result = await agent.run(context)

    assert result.success
    assert client.calls >= 4
    assert [item.spec_id for item in context.test_design_specs] == [
        "SPEC-AUT-001-001-EP-001",
        "SPEC-AUT-001-002-EP-001",
    ]


@pytest.mark.asyncio
async def test_coverage_agent_asks_llm_to_repair_bad_goal_ids():
    client = _RepairingCoverageClient()
    agent = CoverageAgentImpl(llm_client=client)
    context = AgentContext(
        analyzed_requirements=[_analyzed_requirement()],
        risk_analysis=[_risk()],
    )

    result = await agent.run(context)

    assert result.success, result.error
    assert client.calls == 2
    assert [item.coverage_goal_id for item in context.coverage_goals] == ["CG-AUT-001-001"]


@pytest.mark.asyncio
async def test_test_case_agent_repairs_structural_traceability_without_subjective_reviewer():
    client = _BadSpecThenValidCaseClient()
    agent = CaseDraftAgentImpl(llm_client=client)
    context = AgentContext(
        coverage_items=[
            _coverage("COV-AUT-001-001-EP-001"),
        ],
        risk_analysis=[_risk()],
        test_design_specs=[
            _spec("SPEC-AUT-001-001-EP-001", "COV-AUT-001-001-EP-001"),
        ],
    )

    result = await agent.run(context)

    assert result.success, result.error
    assert client.calls == 2
    assert [item.test_id for item in context.test_cases] == [
        "TC-AUT-001-001-EP-001",
    ]
    assert [item.title for item in context.test_cases] == [
        "Borrow book with valid member",
    ]
    assert context.test_cases[0].coverage_item_id == "COV-AUT-001-001-EP-001"
    assert context.test_cases[0].spec_id == "SPEC-AUT-001-001-EP-001"

    exported_keys = set(context.test_cases[0].model_dump(mode="json"))
    assert exported_keys == {
        "test_id",
        "requirement_id",
        "coverage_item_id",
        "spec_id",
        "technique",
        "title",
        "preconditions",
        "input_data",
        "test_steps",
        "expected_result",
        "standard_ref",
        "priority",
        "status",
    }


@pytest.mark.asyncio
async def test_test_case_agent_regenerates_when_llm_returns_empty_cases():
    agent = CaseDraftAgentImpl(llm_client=_EmptyThenValidCaseClient())
    context = AgentContext(
        coverage_items=[_coverage("COV-AUT-001-001-EP-001")],
        risk_analysis=[_risk()],
        test_design_specs=[_spec("SPEC-AUT-001-001-EP-001", "COV-AUT-001-001-EP-001")],
    )

    result = await agent.run(context)

    assert result.success, result.error
    assert len(context.test_cases) == 1
    assert context.test_cases[0].coverage_item_id == "COV-AUT-001-001-EP-001"


class _RepairingSpecClient:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_json(self, prompt: str) -> dict:
        self.calls += 1
        coverage_id = "COV-AUT-001-002-EP-001" if "COV-AUT-001-002-EP-001" in prompt else "COV-AUT-001-001-EP-001"
        spec_id = "SPEC-AUT-001-002-EP-001" if coverage_id == "COV-AUT-001-002-EP-001" else "SPEC-AUT-001-001-EP-001"
        if (
            "already used" in prompt
            or "must match coverage item" in prompt
            or "invalid format" in prompt
        ):
            return {"test_design_specs": [_spec_payload(spec_id, coverage_id)]}
        return {
            "test_design_specs": [
                {
                    "spec_id": "SPEC-DUPLICATE",
                    "coverage_item_id": "COV-LLM-DUPLICATE",
                    "requirement_id": "REQ-LLM-DUPLICATE",
                    "technique": "EP",
                    "design_points": [
                        {
                            "input_values": {"bookId": 1},
                            "expected_behavior": "borrow succeeds",
                            "design_reason": "valid partition",
                        }
                    ],
                    "standard_ref": "ISO/IEC/IEEE 29119-4 EP",
                }
            ]
        }


class _RepairingCoverageClient:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_json(self, prompt: str) -> dict:
        self.calls += 1
        if "invalid format" in prompt or "coverage_goal_id must align" in prompt:
            return {
                "coverage_goals": [
                    {
                        "coverage_goal_id": "CG-AUT-001-001",
                        "requirement_id": "REQ-AUT-001",
                        "goal": "Cover successful borrowing when all preconditions are met.",
                        "related_inputs": ["availableCopies"],
                        "related_conditions": ["availableCopies > 0"],
                        "expected_action": "Borrow succeeds.",
                    }
                ]
            }
        return {
            "coverage_goals": [
                {
                    "coverage_goal_id": "CG-AUT-001-01",
                    "requirement_id": "REQ-AUT-001",
                    "goal": "Cover successful borrowing when all preconditions are met.",
                    "related_inputs": ["availableCopies"],
                    "related_conditions": ["availableCopies > 0"],
                    "expected_action": "Borrow succeeds.",
                }
            ]
        }


class _BadSpecThenValidCaseClient:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_json(self, prompt: str) -> dict:
        if "internal test case quality reviewer" in prompt:
            raise AssertionError("Subjective test case reviewer should not be called.")

        self.calls += 1
        if self.calls == 1:
            return {
                "test_cases": [
                    _case(
                        "Borrow book with valid member",
                        1,
                        "TC-AUT-001-001-EP-001",
                        "COV-AUT-001-001-EP-001",
                        "SPEC-AUT-999-001-EP-001",
                    )
                ]
            }
        return {
            "test_cases": [
                _case(
                    "Borrow book with valid member",
                    1,
                    "TC-AUT-001-001-EP-001",
                    "COV-AUT-001-001-EP-001",
                    "SPEC-AUT-001-001-EP-001",
                )
            ]
        }


class _EmptyThenValidCaseClient:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_json(self, prompt: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {"test_cases": []}
        return {
            "test_cases": [
                _case(
                    "Borrow book with valid member",
                    1,
                    "TC-AUT-001-001-EP-001",
                    "COV-AUT-001-001-EP-001",
                    "SPEC-AUT-001-001-EP-001",
                )
            ]
        }


def _coverage(coverage_item_id: str) -> CoverageItemModel:
    return CoverageItemModel.model_validate(
        {
            "coverage_item_id": coverage_item_id,
            "coverage_goal_id": "CG-AUT-001-001",
            "requirement_id": "REQ-AUT-001",
            "technique": "EP",
            "description": "Cover borrow availability partitions.",
            "conditions": ["Borrow request is submitted"],
            "data_ranges": ["availableCopies > 0", "availableCopies = 0"],
            "input_fields": ["availableCopies"],
            "expected_action": "System accepts or rejects the borrow request.",
            "strategy_rationale": "EP separates available and unavailable books.",
            "technique_reason": "EP covers valid and invalid availability partitions.",
        }
    )


def _risk() -> RiskAnalysisItem:
    return RiskAnalysisItem.model_validate(
        {
            "requirement_id": "REQ-AUT-001",
            "impact": 4,
            "likelihood": 3,
            "risk_score": 12,
            "risk_level": "Medium",
            "test_priority": "P2",
            "risk_reason": "Borrowing is a core library workflow.",
        }
    )


def _analyzed_requirement() -> AnalyzedRequirement:
    return AnalyzedRequirement.model_validate(
        {
            "requirement_id": "REQ-AUT-001",
            "module": "Borrowing",
            "description": "The system shall allow borrowing when copies are available.",
            "input_fields": ["availableCopies"],
            "data_ranges": ["availableCopies > 0", "availableCopies = 0"],
            "conditions": ["Book exists", "Member exists"],
            "business_rules": ["Borrow only when copies are available"],
            "expected_action": "Create borrowing record or reject request.",
        }
    )


def _spec(spec_id: str, coverage_item_id: str) -> DesignSpecModel:
    return DesignSpecModel.model_validate(
        {
            "spec_id": spec_id,
            "coverage_item_id": coverage_item_id,
            "requirement_id": "REQ-AUT-001",
            "technique": "EP",
            "design_points": [
                {
                    "input_values": {"availableCopies": 1},
                    "expected_behavior": "borrow succeeds",
                    "design_reason": "valid partition",
                }
            ],
            "standard_ref": "ISO/IEC/IEEE 29119-4 EP",
        }
    )


def _spec_payload(spec_id: str, coverage_item_id: str) -> dict:
    return {
        "spec_id": spec_id,
        "coverage_item_id": coverage_item_id,
        "requirement_id": "REQ-AUT-001",
        "technique": "EP",
        "design_points": [
            {
                "input_values": {"bookId": 1},
                "expected_behavior": "borrow succeeds",
                "design_reason": "valid partition",
            }
        ],
        "standard_ref": "ISO/IEC/IEEE 29119-4 EP",
    }


def _case(
    title: str,
    available_copies: int,
    test_id: str,
    coverage_item_id: str,
    spec_id: str,
) -> dict:
    expected = "Borrow request is accepted." if available_copies else "Borrow request is rejected."
    return {
        "test_id": test_id,
        "requirement_id": "REQ-AUT-001",
        "coverage_item_id": coverage_item_id,
        "spec_id": spec_id,
        "technique": "EP",
        "title": title,
        "preconditions": ["Book exists", "Member exists"],
        "input_data": {"availableCopies": available_copies},
        "test_steps": ["Submit a borrow request."],
        "expected_result": expected,
        "standard_ref": "ISO/IEC/IEEE 29119-4 EP",
        "priority": "P2",
        "status": "Draft",
    }
