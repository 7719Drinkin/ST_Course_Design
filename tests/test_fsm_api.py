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

from main import create_app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_fsm_api_generates_model_cases_mermaid_and_traceability(client: TestClient):
    response = client.post(
        "/fsm",
        json={
            "requirement_id": "REQ-AUT-FSM-API",
            "requirement_text": "The system shall create a borrowing record when a member borrows an available book.",
            "strategies": ["ALL_STATES", "ALL_TRANSITIONS"],
            "max_depth": 6,
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["fsm_model"]["initial_state"] == "FSM-STATE-001"
    assert payload["data"]["mermaid"].startswith("stateDiagram-v2")
    assert {case["technique"] for case in payload["data"]["test_cases"]} == {"FSM"}
    assert payload["data"]["traceability"]["test_cases"]


def test_fsm_api_rejects_invalid_strategy(client: TestClient):
    response = client.post(
        "/fsm",
        json={
            "requirement_id": "REQ-AUT-FSM-BAD",
            "requirement_text": "The system shall create a borrowing record.",
            "strategies": ["BAD_STRATEGY"],
        },
    )

    assert response.status_code == 422
