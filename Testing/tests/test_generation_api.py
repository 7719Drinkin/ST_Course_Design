from __future__ import annotations

import pytest
from fastapi import FastAPI


fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

import backend.agent as backend_agent  # noqa: E402
from backend.app.modules.generation.router import router as generation_router  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(generation_router)
    return TestClient(app)


def test_generate_uses_mock_agent(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        return _agent_result("REQ-AUT-001", "EP")

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-001",
            "requirement_text": "The system shall allow a registered user to borrow a book only if availableCopies > 0.",
            "techniques": ["EP"],
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["metadata"]["agent_used"] is True
    assert payload["metadata"]["case_count"] == 1
    assert payload["data"]["test_cases"][0]["test_id"] == "TC-MOCK-REQ-AUT-001-EP-001"
    assert {case["technique"] for case in payload["data"]["test_cases"]} == {"EP"}


def test_generate_agent_exception_returns_error(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        raise RuntimeError("mock agent exploded")

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-001",
            "requirement_text": "The system shall allow a registered user to borrow a book only if availableCopies > 0.",
            "techniques": ["EP"],
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["metadata"]["agent_used"] is True
    assert payload["metadata"]["case_count"] == 0
    assert payload["errors"] == ["mock agent exploded"]
    assert payload["data"]["test_cases"] == []


def test_generate_empty_agent_cases_returns_error(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_blackbox_tests(requirement_text: str, rag_context: str | None = None) -> dict:
        return {"success": True, "data": {"test_cases": []}, "errors": []}

    monkeypatch.setattr(backend_agent, "generate_blackbox_tests", fake_generate_blackbox_tests)

    response = client.post(
        "/generate",
        json={
            "requirement_id": "REQ-AUT-001",
            "requirement_text": "The system shall allow a registered user to borrow a book only if availableCopies > 0.",
            "techniques": ["EP"],
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["errors"] == ["empty test_cases from Agent"]
    assert payload["data"]["test_cases"] == []


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
