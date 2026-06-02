from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
FastAPI = fastapi.FastAPI

fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.modules.optimize_export.router import router as optimize_export_router  # noqa: E402
from app.modules.store import workflow_store  # noqa: E402
from app.modules.test_design.router import router as design_router  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(design_router)
    app.include_router(optimize_export_router)
    return TestClient(app)


def test_oracle_api_reads_stored_results_and_exports_json(client: TestClient):
    session_id = "SESSION-FR5-API"
    _seed_oracle_export_store(session_id)

    response = client.post(
        "/oracle",
        json={
            "session_id": session_id,
            "test_cases": [],
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["session_id"] == session_id
    assert len(payload["oracle_results"]) == 1
    oracle_result = payload["oracle_results"][0]
    assert oracle_result["test_id"] == "TC-AUT-001-001-EP-001"
    assert oracle_result["expected_result_suggestion"] == "Borrow request is rejected and no borrowing record is created."
    assert oracle_result["confidence"] >= 0.7
    assert oracle_result["needs_review"] is False
    assert payload["prompt_evidence"]

    export_response = client.get(
        "/export",
        params={"session_id": session_id, "format": "json"},
    )
    assert export_response.status_code == 200
    export_bundle = export_response.json()["export_bundle"]
    assert export_bundle["oracle_results"][0]["test_id"] == "TC-AUT-001-001-EP-001"
    assert (
        export_bundle["oracle_results"][0]["expected_result_suggestion"]
        == "Borrow request is rejected and no borrowing record is created."
    )


def test_oracle_api_returns_empty_results_for_unfinished_session(client: TestClient):
    session_id = "SESSION-FR5-EMPTY"
    workflow_store.clear_keys(session_id, ["oracle_results", "prompt_evidence"])

    response = client.post(
        "/oracle",
        json={"session_id": session_id, "test_cases": []},
    )

    assert response.status_code == 200
    assert response.json()["oracle_results"] == []


def test_oracle_results_are_exported_as_csv_and_xlsx(client: TestClient):
    session_id = "SESSION-FR5-EXPORT-FILES"
    _seed_oracle_export_store(session_id)

    csv_response = client.get(
        "/export",
        params={"session_id": session_id, "format": "csv"},
    )
    assert csv_response.status_code == 200
    csv_text = csv_response.content.decode("utf-8-sig")
    assert "oracle_result" in csv_text
    assert "Borrow request is rejected" in csv_text

    xlsx_response = client.get(
        "/export",
        params={"session_id": session_id, "format": "xlsx"},
    )
    assert xlsx_response.status_code == 200
    assert xlsx_response.content.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(xlsx_response.content)) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
    assert "oracle_results" in workbook_xml


def _seed_oracle_export_store(session_id: str) -> None:
    workflow_store.clear_keys(
        session_id,
        [
            "requirements",
            "risk_results",
            "coverage_items",
            "test_design_specs",
            "test_cases",
            "fsm_test_cases",
            "oracle_results",
            "analysis_results",
            "prompt_evidence",
            "optimization_result",
            "fsm",
            "revisions",
        ],
    )
    workflow_store.save_many(
        session_id,
        "requirements",
        [
            {
                "requirement_id": "REQ-AUT-001",
                "module": "Borrowing",
                "description": "Reject borrowing when the target book has no available copies.",
                "raw_text": "If available copies are zero, the system rejects the borrow request.",
            }
        ],
        "requirement_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "risk_results",
        [
            {
                "target_id": "REQ-AUT-001",
                "target_type": "requirement",
                "impact": 4,
                "likelihood": 3,
                "risk_score": 12,
                "risk_level": "Medium",
                "test_priority": "P2",
                "reason": "Borrowing is a core AUT workflow.",
                "evidence": [],
            }
        ],
        "target_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "coverage_items",
        [
            {
                "coverage_item_id": "COV-AUT-001-001-EP-001",
                "coverage_goal_id": "CG-AUT-001-001",
                "requirement_id": "REQ-AUT-001",
                "technique": "EP",
                "description": "Cover unavailable book partition.",
                "conditions": ["availableCopies equals 0"],
                "data_ranges": ["availableCopies = 0"],
                "input_fields": ["availableCopies"],
                "expected_action": "System rejects the borrow request.",
            }
        ],
        "coverage_item_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "test_design_specs",
        [
            {
                "spec_id": "SPEC-AUT-001-001-EP-001",
                "coverage_item_id": "COV-AUT-001-001-EP-001",
                "requirement_id": "REQ-AUT-001",
                "technique": "EP",
                "design_points": [{"input_values": {"availableCopies": 0}, "expected_behavior": "reject borrow"}],
                "standard_ref": "ISO/IEC/IEEE 29119-4 EP",
            }
        ],
        "spec_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "test_cases",
        [
            {
                "test_id": "TC-AUT-001-001-EP-001",
                "requirement_id": "REQ-AUT-001",
                "coverage_item_id": "COV-AUT-001-001-EP-001",
                "spec_id": "SPEC-AUT-001-001-EP-001",
                "technique": "EP",
                "title": "Reject borrowing when available copies are zero",
                "preconditions": ["Book exists", "Member exists"],
                "input_data": {"availableCopies": 0},
                "test_steps": ["Submit a borrow request for a book with zero available copies."],
                "expected_result": "Borrow request is rejected and no borrowing record is created.",
                "standard_ref": "ISO/IEC/IEEE 29119-4 EP",
                "priority": "P2",
                "status": "Draft",
            }
        ],
        "test_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "oracle_results",
        [
            {
                "test_id": "TC-AUT-001-001-EP-001",
                "expected_result_suggestion": "Borrow request is rejected and no borrowing record is created.",
                "confidence": 0.91,
                "explanation": "The requirement explicitly rejects borrowing when available copies are zero.",
                "needs_review": False,
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
                "evidence_id": "PE-ORACLE-001",
                "session_id": session_id,
                "prompt_name": "oracle_generation",
                "target_id": "TC-AUT-001-001-EP-001",
                "input": {},
                "output": {},
                "note": "Stored oracle prompt evidence generated by DeepSeek.",
                "created_at": "2026-06-02T00:00:00Z",
            }
        ],
        "evidence_id",
        replace_all=True,
    )
