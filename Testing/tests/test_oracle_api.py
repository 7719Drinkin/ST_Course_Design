from __future__ import annotations

import sys
import io
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI


fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from backend.agent.pipeline import AgentPipeline  # noqa: E402
from app.modules.store import workflow_store  # noqa: E402
from app.modules.optimize_export.router import router as optimize_export_router  # noqa: E402
from app.modules.test_design.router import router as design_router  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(design_router)
    app.include_router(optimize_export_router)
    return TestClient(app)


def test_oracle_api_returns_results_evidence_and_persists(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fail_oracle_prompt(self, *args, **kwargs):
        raise RuntimeError("模拟 Oracle prompt 不可用")

    monkeypatch.setattr(AgentPipeline, "generate_oracles", fail_oracle_prompt)
    session_id = "SESSION-FR5-API"

    response = client.post(
        "/oracle",
        json={
            "session_id": session_id,
            "test_cases": [
                {
                    "test_id": "TC-AUT-001",
                    "requirement_id": "REQ-AUT-001",
                    "coverage_item_id": "COV-AUT-001",
                    "technique": "BVA",
                    "title": "库存为 0 时拒绝借阅",
                    "input_data": {"availableCopies": 0},
                    "test_steps": ["提交 availableCopies = 0 的借阅请求。"],
                    "expected_result": "",
                }
            ],
            "requirements": [
                {
                    "requirement_id": "REQ-AUT-001",
                    "description": "只有 availableCopies > 0 时借阅才会成功。",
                    "expected_action": "借阅请求被拒绝，且系统不创建借阅记录。",
                }
            ],
            "source_context_ids": ["CTX-FR5-001"],
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["session_id"] == session_id
    assert len(payload["oracle_results"]) == 1
    oracle_result = payload["oracle_results"][0]
    assert oracle_result["test_id"] == "TC-AUT-001"
    assert oracle_result["expected_result_suggestion"] == "借阅请求被拒绝，且系统不创建借阅记录。"
    assert oracle_result["confidence"] >= 0.7
    assert oracle_result["needs_review"] is False
    assert payload["prompt_evidence"]
    assert "确定性 Oracle 兜底" in payload["prompt_evidence"][0]["note"]

    bundle = workflow_store.export_bundle(session_id)
    assert bundle["test_cases"][0]["test_id"] == "TC-AUT-001"
    assert bundle["oracle_results"][0]["test_id"] == "TC-AUT-001"
    assert bundle["prompt_evidence"]

    export_response = client.get(
        "/export",
        params={"session_id": session_id, "format": "json"},
    )
    assert export_response.status_code == 200
    export_bundle = export_response.json()["export_bundle"]
    assert export_bundle["oracle_results"][0]["test_id"] == "TC-AUT-001"
    assert (
        export_bundle["oracle_results"][0]["expected_result_suggestion"]
        == "借阅请求被拒绝，且系统不创建借阅记录。"
    )


def test_oracle_api_marks_review_when_context_is_insufficient(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fail_oracle_prompt(self, *args, **kwargs):
        raise RuntimeError("模拟 Oracle prompt 不可用")

    monkeypatch.setattr(AgentPipeline, "generate_oracles", fail_oracle_prompt)

    response = client.post(
        "/oracle",
        json={
            "session_id": "SESSION-FR5-REVIEW",
            "test_cases": [
                {
                    "test_id": "TC-AUT-REVIEW",
                    "requirement_id": "REQ-AUT-MISSING",
                    "coverage_item_id": "COV-AUT-REVIEW",
                    "technique": "EP",
                    "test_steps": ["执行一个缺少需求依据的测试步骤。"],
                    "expected_result": "",
                }
            ],
        },
    )

    payload = response.json()
    assert response.status_code == 200
    oracle_result = payload["oracle_results"][0]
    assert oracle_result["test_id"] == "TC-AUT-REVIEW"
    assert oracle_result["confidence"] < 0.7
    assert oracle_result["needs_review"] is True
    assert "人工复核" in oracle_result["expected_result_suggestion"]


def test_oracle_results_are_exported_as_csv_and_xlsx(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fail_oracle_prompt(self, *args, **kwargs):
        raise RuntimeError("模拟 Oracle prompt 不可用")

    monkeypatch.setattr(AgentPipeline, "generate_oracles", fail_oracle_prompt)
    session_id = "SESSION-FR5-EXPORT-FILES"

    oracle_response = client.post(
        "/oracle",
        json={
            "session_id": session_id,
            "test_cases": [
                {
                    "test_id": "TC-AUT-CSV",
                    "requirement_id": "REQ-AUT-CSV",
                    "coverage_item_id": "COV-AUT-CSV",
                    "technique": "EP",
                    "test_steps": ["提交无效借阅请求。"],
                    "expected_result": "系统拒绝无效借阅请求。",
                }
            ],
        },
    )
    assert oracle_response.status_code == 200

    csv_response = client.get(
        "/export",
        params={"session_id": session_id, "format": "csv"},
    )
    assert csv_response.status_code == 200
    csv_text = csv_response.content.decode("utf-8-sig")
    assert "oracle_result" in csv_text
    assert "系统拒绝无效借阅请求。" in csv_text

    xlsx_response = client.get(
        "/export",
        params={"session_id": session_id, "format": "xlsx"},
    )
    assert xlsx_response.status_code == 200
    assert xlsx_response.content.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(xlsx_response.content)) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
    assert "oracle_results" in workbook_xml
