from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

from backend.app.modules.generation import service as generation_service
from backend.app.modules.generation.schemas import GenerateRequest

try:
    from backend.app.modules.generation.router import router
except ModuleNotFoundError:
    router = None


def test_generate_router_exposes_generate_path():
    if router is None:
        return
    paths = {route.path for route in router.routes}
    assert "/generate" in paths


def test_deterministic_mode_does_not_call_agent():
    request = GenerateRequest(
        requirement_id="REQ-GEN-DET",
        requirement_text="The system shall accept age between 18 and 60.",
        generation_mode="deterministic",
        techniques=["BVA"],
    )

    with patch.object(
        generation_service,
        "generate_blackbox_tests",
        new=AsyncMock(side_effect=AssertionError("Agent should not be called")),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert response.metadata.agent_used is False
    assert response.metadata.deterministic_used is True
    assert {case["technique"] for case in response.data["test_cases"]} == {"BVA"}


def test_agent_mode_does_not_call_deterministic_when_agent_is_valid():
    request = GenerateRequest(
        requirement_id="REQ-GEN-AGT",
        requirement_text="The system shall list all books.",
        generation_mode="agent",
        techniques=["EP"],
    )

    with patch.object(
        generation_service,
        "generate_blackbox_tests",
        new=AsyncMock(return_value=_agent_result("REQ-GEN-AGT", "EP")),
    ), patch.object(
        generation_service,
        "generate_deterministic_blackbox_tests",
        new=Mock(side_effect=AssertionError("Deterministic should not be called")),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert response.metadata.agent_used is True
    assert response.metadata.deterministic_used is False
    assert response.metadata.fallback_used is False
    assert response.data["test_cases"][0]["standard_ref"]


def test_agent_first_uses_agent_when_result_is_valid():
    request = GenerateRequest(
        requirement_id="REQ-GEN-FIRST",
        requirement_text="The system shall list all books.",
        generation_mode="agent_first",
        techniques=["EP"],
    )

    with patch.object(
        generation_service,
        "generate_blackbox_tests",
        new=AsyncMock(return_value=_agent_result("REQ-GEN-FIRST", "EP")),
    ), patch.object(
        generation_service,
        "generate_deterministic_blackbox_tests",
        new=Mock(side_effect=AssertionError("Fallback should not be called")),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert response.metadata.agent_used is True
    assert response.metadata.deterministic_used is False
    assert response.metadata.fallback_used is False
    assert response.metadata.case_count == 1


def test_agent_first_falls_back_when_agent_returns_success_false():
    request = GenerateRequest(
        requirement_id="REQ-GEN-FALLBACK",
        requirement_text="The system shall accept copies > 0.",
        generation_mode="agent_first",
        techniques=["BVA"],
    )

    with patch.object(
        generation_service,
        "generate_blackbox_tests",
        new=AsyncMock(return_value={"success": False, "error": "agent unavailable"}),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert response.metadata.agent_used is True
    assert response.metadata.deterministic_used is True
    assert response.metadata.fallback_used is True
    assert response.metadata.fallback_reason == "invalid_agent_result"
    assert response.data["test_cases"]


def test_agent_mode_rejects_agent_technique_outside_request():
    request = GenerateRequest(
        requirement_id="REQ-GEN-FILTER",
        requirement_text="The system shall list all books.",
        generation_mode="agent",
        techniques=["EP"],
    )

    with patch.object(
        generation_service,
        "generate_blackbox_tests",
        new=AsyncMock(return_value=_agent_result("REQ-GEN-FILTER", "BVA")),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is False
    assert response.metadata.deterministic_used is False
    assert response.metadata.fallback_reason == "invalid_agent_result"


def test_hybrid_merges_agent_and_deterministic_cases():
    request = GenerateRequest(
        requirement_id="REQ-GEN-HYBRID",
        requirement_text="The system shall accept age between 18 and 60.",
        generation_mode="hybrid",
        techniques=["EP", "BVA"],
    )

    with patch.object(
        generation_service,
        "generate_blackbox_tests",
        new=AsyncMock(return_value=_agent_result("REQ-GEN-HYBRID", "EP")),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert response.metadata.agent_used is True
    assert response.metadata.deterministic_used is True
    assert response.metadata.fallback_used is False
    assert {"EP", "BVA"}.issubset({case["technique"] for case in response.data["test_cases"]})


def _agent_result(requirement_id: str, technique: str) -> dict:
    return {
        "success": True,
        "data": {
            "coverage_items": [
                {
                    "coverage_item_id": f"COV-AGT-{requirement_id}-{technique}-001",
                    "coverage_goal_id": f"GOAL-AGT-{requirement_id}-{technique}",
                    "requirement_id": requirement_id,
                    "technique": technique,
                    "description": "Agent coverage item.",
                    "conditions": [],
                    "data_ranges": [],
                    "input_fields": [],
                    "expected_action": "Return expected response.",
                    "strategy_rationale": "Agent rationale.",
                }
            ],
            "test_design_specs": [],
            "test_cases": [
                {
                    "test_id": f"TC-AGT-{requirement_id}-{technique}-001",
                    "requirement_id": requirement_id,
                    "coverage_item_id": f"COV-AGT-{requirement_id}-{technique}-001",
                    "spec_id": f"SPEC-AGT-{requirement_id}-{technique}-001",
                    "technique": technique,
                    "title": "Agent generated case",
                    "preconditions": [],
                    "input_data": {},
                    "test_steps": ["Execute request."],
                    "expected_result": "Return expected response.",
                    "standard_ref": "",
                    "status": "Draft",
                }
            ],
        },
    }
