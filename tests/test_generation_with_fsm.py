from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from backend.app.modules.generation import service as generation_service
from backend.app.modules.generation.schemas import GenerateRequest


def test_generate_with_fsm_only_returns_fsm_cases_and_model():
    request = GenerateRequest(
        requirement_id="REQ-GEN-FSM-ONLY",
        requirement_text="The system shall create a borrowing record when a member borrows an available book.",
        techniques=["FSM"],
        generation_mode="deterministic",
    )

    with patch.object(
        generation_service.agent_module,
        "generate_blackbox_tests",
        new=AsyncMock(side_effect=AssertionError("deterministic mode must not call LLM agent")),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert response.metadata.agent_used is False
    assert response.metadata.deterministic_used is True
    assert response.data["fsm_model"]["model_id"] == "FSM-MODEL-001"
    assert {case["technique"] for case in response.data["test_cases"]} == {"FSM"}


def test_generate_with_ep_bva_dt_fsm_returns_four_techniques():
    request = GenerateRequest(
        requirement_id="REQ-GEN-ALL-FSM",
        requirement_text=(
            "The system shall allow a member age between 18 and 60 to borrow a book "
            "when book exists, member exists, and availableCopies > 0."
        ),
        context={"business_rules": ["Book exists", "Member exists", "availableCopies > 0"]},
        techniques=["EP", "BVA", "DT", "FSM"],
        generation_mode="deterministic",
    )

    response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert {"EP", "BVA", "DT", "FSM"}.issubset(
        {case["technique"] for case in response.data["test_cases"]}
    )
    assert response.data["fsm_model"]["states"]
    assert any(item["coverage_item_id"].startswith("COV-AUT-FSM-") for item in response.data["coverage_items"])


def test_agent_first_supplements_fsm_without_blackbox_deterministic_fallback():
    request = GenerateRequest(
        requirement_id="REQ-GEN-FSM-SUPPLEMENT",
        requirement_text="The system shall create a borrowing record when a member borrows an available book.",
        techniques=["EP", "FSM"],
        generation_mode="agent_first",
    )

    with patch.object(
        generation_service.agent_module,
        "generate_blackbox_tests",
        new=AsyncMock(return_value=_agent_result("REQ-GEN-FSM-SUPPLEMENT", "EP")),
    ), patch.object(
        generation_service,
        "generate_deterministic_blackbox_tests",
        side_effect=AssertionError("blackbox deterministic fallback should not run"),
    ):
        response = asyncio.run(generation_service.generate_test_cases(request))

    assert response.success is True
    assert response.metadata.agent_used is True
    assert response.metadata.deterministic_used is True
    assert {"EP", "FSM"}.issubset({case["technique"] for case in response.data["test_cases"]})


def test_generate_with_fsm_is_reproducible():
    request = GenerateRequest(
        requirement_id="REQ-GEN-FSM-STABLE",
        requirement_text="A member borrows a book when availableCopies > 0 and later returns it.",
        techniques=["FSM"],
        generation_mode="deterministic",
    )

    first = asyncio.run(generation_service.generate_test_cases(request))
    second = asyncio.run(generation_service.generate_test_cases(request))

    assert first.dict() == second.dict()


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
