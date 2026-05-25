from __future__ import annotations

import sys
from pathlib import Path

import pytest


fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import backend.agent as backend_agent  # noqa: E402
from main import create_app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_generate_agent_first_uses_mock_agent_by_default(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        return _agent_result("REQ-AUT-001", "EP")

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-001",
            "requirement_text": "The system shall allow a registered user to borrow a book only if availableCopies > 0.",
            "techniques": ["EP"],
            "generation_mode": "agent_first",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["metadata"]["agent_used"] is True
    assert payload["metadata"]["deterministic_used"] is False
    assert payload["metadata"]["fallback_used"] is False
    assert payload["data"]["test_cases"][0]["test_id"] == "TC-MOCK-REQ-AUT-001-EP-001"
    assert {case["technique"] for case in payload["data"]["test_cases"]} == {"EP"}


def test_generate_agent_exception_falls_back_to_deterministic(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        raise RuntimeError("mock agent exploded")

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-001",
            "requirement_text": "The system shall allow a registered user to borrow a book only if availableCopies > 0.",
            "techniques": ["EP"],
            "generation_mode": "agent_first",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["metadata"]["agent_used"] is True
    assert payload["metadata"]["deterministic_used"] is True
    assert payload["metadata"]["fallback_used"] is True
    assert payload["metadata"]["fallback_reason"] == "agent_exception"
    assert payload["data"]["test_cases"]


def test_generate_empty_agent_cases_fall_back_to_deterministic(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        return {"success": True, "data": {"test_cases": []}, "errors": []}

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-001",
            "requirement_text": "The system shall allow a registered user to borrow a book only if availableCopies > 0.",
            "techniques": ["EP"],
            "generation_mode": "agent_first",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["metadata"]["fallback_used"] is True
    assert payload["metadata"]["fallback_reason"] == "empty_test_cases"
    assert payload["metadata"]["deterministic_used"] is True
    assert payload["data"]["test_cases"]


def test_generate_agent_mode_does_not_fallback(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        raise RuntimeError("agent-only failure")

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-001",
            "requirement_text": "The system shall allow a registered user to borrow a book only if availableCopies > 0.",
            "techniques": ["EP"],
            "generation_mode": "agent",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["metadata"]["deterministic_used"] is False
    assert payload["metadata"]["fallback_used"] is False


def test_generate_deterministic_mode_does_not_call_agent(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        raise AssertionError("Agent must not be called in deterministic mode")

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-002",
            "requirement_text": "The system shall accept password length between 8 and 20 characters.",
            "techniques": ["BVA"],
            "generation_mode": "deterministic",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["metadata"]["agent_used"] is False
    assert payload["metadata"]["deterministic_used"] is True
    assert {case["technique"] for case in payload["data"]["test_cases"]} == {"BVA"}
    assert {7, 8, 9, 19, 20, 21}.issubset(_numeric_values(payload["data"]["test_cases"]))


def test_generate_deterministic_fsm_returns_state_model(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        raise AssertionError("Agent must not be called in deterministic mode")

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-FSM",
            "requirement_text": "The system shall create a borrowing record when a member borrows an available book.",
            "techniques": ["FSM"],
            "generation_mode": "deterministic",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["metadata"]["agent_used"] is False
    assert payload["metadata"]["deterministic_used"] is True
    assert payload["data"]["fsm_model"]["initial_state"] == "FSM-STATE-001"
    assert {case["technique"] for case in payload["data"]["test_cases"]} == {"FSM"}


def test_generate_rejects_invalid_technique(client: TestClient):
    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-BAD",
            "requirement_text": "The system shall do something.",
            "techniques": ["EP", "NOT_A_TECHNIQUE"],
            "generation_mode": "deterministic",
        },
    )

    assert response.status_code == 422


def _agent_result(requirement_id: str, technique: str) -> dict:
    return {
        "success": True,
        "data": {
            "coverage_items": [
                {
                    "coverage_item_id": f"COV-MOCK-{requirement_id}-{technique}-001",
                    "coverage_goal_id": f"GOAL-MOCK-{requirement_id}-{technique}",
                    "requirement_id": requirement_id,
                    "technique": technique,
                    "description": "Mock Agent coverage item.",
                    "conditions": [],
                    "data_ranges": [],
                    "input_fields": ["availableCopies"],
                    "expected_action": "Return mock Agent result.",
                    "strategy_rationale": "Mocked Agent preferred path.",
                }
            ],
            "test_cases": [
                {
                    "test_id": f"TC-MOCK-{requirement_id}-{technique}-001",
                    "requirement_id": requirement_id,
                    "coverage_item_id": f"COV-MOCK-{requirement_id}-{technique}-001",
                    "spec_id": f"SPEC-MOCK-{requirement_id}-{technique}-001",
                    "technique": technique,
                    "title": "Mock Agent generated EP case",
                    "preconditions": [],
                    "input_data": {"source": "mock_agent"},
                    "test_steps": ["Execute mock Agent test case."],
                    "expected_result": "Return mock Agent result.",
                    "standard_ref": "Mock Agent standard reference.",
                    "status": "Draft",
                }
            ],
            "test_design_specs": [],
        },
    }


def _numeric_values(test_cases: list[dict]) -> set[int | float]:
    values: set[int | float] = set()
    for case in test_cases:
        for value in case.get("input_data", {}).values():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.add(value)
    return values
