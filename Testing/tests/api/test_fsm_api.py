from __future__ import annotations

import sys
from pathlib import Path

import pytest


fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from main import create_app  # noqa: E402
from app.modules.store import workflow_store  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_fsm_api_returns_fr4_contract_model_cases_mermaid_and_traceability(client: TestClient):
    session_id = "SESSION-FR4"
    workflow_store.clear_keys(session_id, ["fsm", "fsm_test_cases", "prompt_evidence"])
    workflow_store.save_object(
        session_id,
        "fsm",
        {
            "states": ["AVAILABLE", "BORROWED", "RETURNED"],
            "transitions": [
                {
                    "from": "AVAILABLE",
                    "to": "BORROWED",
                    "event": "borrow",
                    "condition": "book is available",
                    "action": "create borrowing record",
                }
            ],
            "coverage_paths": ["AVAILABLE -> BORROWED -> RETURNED"],
            "coverage": {"all_states": ["AVAILABLE", "BORROWED", "RETURNED"], "all_transitions": ["AVAILABLE -> BORROWED"]},
            "mermaid": "stateDiagram-v2\n  AVAILABLE --> BORROWED: borrow",
        },
    )
    workflow_store.save_many(
        session_id,
        "fsm_test_cases",
        [
            {
                "test_id": "TC-AUT-FSM-001",
                "requirement_id": "REQ-AUT-001",
                "coverage_item_id": "COV-AUT-FSM-001",
                "strategy_id": "STR-AUT-FSM-001",
                "technique": "FSM",
                "title": "Borrow available book",
                "preconditions": ["Book is AVAILABLE"],
                "input_data": {"event": "borrow"},
                "test_steps": ["Borrow the available book."],
                "expected_result": "State changes from AVAILABLE to BORROWED.",
                "standard_ref": "FSM state transition testing",
                "risk_level": "Medium",
                "status": "Draft",
            }
        ],
        "test_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "prompt_evidence",
        [
            {
                "evidence_id": "PE-FSM-001",
                "session_id": session_id,
                "prompt_name": "fsm_modeling",
                "target_id": "REQ-AUT-001",
                "input": {},
                "output": {},
                "note": "Stored FSM prompt evidence.",
                "created_at": "2026-06-02T00:00:00Z",
            }
        ],
        "evidence_id",
        replace_all=True,
    )

    response = client.post(
        "/fsm",
        json={
            "session_id": session_id,
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
    assert payload["session_id"] == session_id
    assert payload["fsm"]["states"]
    assert payload["fsm"]["transitions"]
    assert payload["fsm"]["transitions"][0]["from"]
    assert payload["fsm"]["transitions"][0]["to"]
    assert payload["fsm"]["coverage_paths"]
    assert payload["fsm"]["mermaid"].startswith("stateDiagram-v2")
    assert {case["technique"] for case in payload["test_cases"]} == {"FSM"}
    assert all(case["requirement_id"] == "REQ-AUT-001" for case in payload["test_cases"])
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
