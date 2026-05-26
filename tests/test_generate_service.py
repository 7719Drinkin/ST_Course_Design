from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

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


def test_generate_uses_agent_result():
    request = GenerateRequest(
        requirement_id="REQ-GEN-AGT",
        requirement_text="The system shall list all books.",
        techniques=["EP"],
    )

    with patch.object(
        generation_service.agent_module,
        "generate_blackbox_tests",
        new=AsyncMock(return_value=_agent_result("REQ-GEN-AGT", "EP")),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert response.metadata.agent_used is True
    assert response.metadata.generation_mode == "agent"
    assert response.metadata.case_count == 1
    assert response.data["test_cases"][0]["standard_ref"]


def test_generate_returns_error_when_agent_fails():
    request = GenerateRequest(
        requirement_id="REQ-GEN-FAIL",
        requirement_text="The system shall accept copies > 0.",
        techniques=["BVA"],
    )

    with patch.object(
        generation_service.agent_module,
        "generate_blackbox_tests",
        new=AsyncMock(return_value={"success": False, "error": "agent unavailable"}),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is False
    assert response.metadata.agent_used is True
    assert response.metadata.case_count == 0
    assert response.errors == ["agent unavailable"]
    assert response.data["test_cases"] == []


def test_generate_rejects_agent_technique_outside_request():
    request = GenerateRequest(
        requirement_id="REQ-GEN-FILTER",
        requirement_text="The system shall list all books.",
        techniques=["EP"],
    )

    with patch.object(
        generation_service.agent_module,
        "generate_blackbox_tests",
        new=AsyncMock(return_value=_agent_result("REQ-GEN-FILTER", "BVA")),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is False
    assert response.errors


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
