from __future__ import annotations

import sys
from pathlib import Path

import pytest


fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from main import create_app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_fsm_api_returns_fr4_contract_model_cases_mermaid_and_traceability(client: TestClient):
    response = client.post(
        "/fsm",
        json={
            "session_id": "SESSION-FR4",
            "requirements": [
                {
                    "requirement_id": "REQ-AUT-FSM-API",
                    "raw_text": (
                        "The system shall create a borrowing record when a member "
                        "borrows an available book."
                    ),
                }
            ],
            "state_candidates": ["AVAILABLE", "BORROWED", "RETURNED", "REJECTED"],
            "strategies": ["ALL_STATES", "ALL_TRANSITIONS"],
            "max_depth": 6,
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["session_id"] == "SESSION-FR4"
    assert payload["fsm"]["states"]
    assert payload["fsm"]["transitions"]
    assert payload["fsm"]["transitions"][0]["from"]
    assert payload["fsm"]["transitions"][0]["to"]
    assert payload["fsm"]["coverage_paths"]
    assert payload["fsm"]["mermaid"].startswith("stateDiagram-v2")
    assert {case["technique"] for case in payload["test_cases"]} == {"FSM"}
    assert all(case["requirement_id"] == "REQ-AUT-FSM-API" for case in payload["test_cases"])
    assert all(case["coverage_item_id"] for case in payload["test_cases"])
    assert payload["prompt_evidence"]


def test_fsm_api_rejects_invalid_strategy(client: TestClient):
    response = client.post(
        "/fsm",
        json={
            "session_id": "SESSION-FR4-BAD",
            "requirements": [
                {
                    "requirement_id": "REQ-AUT-FSM-BAD",
                    "raw_text": "The system shall create a borrowing record.",
                }
            ],
            "strategies": ["BAD_STRATEGY"],
        },
    )

    assert response.status_code == 422
