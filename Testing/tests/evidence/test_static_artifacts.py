"""Static checks that can run in CI without the live AUT or LLM services."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent


def test_current_shared_documents_exist():
    required_docs = [
        "docs/develop/branch_policy.md",
        "docs/develop/前端展示对接文档.md",
        "docs/develop/后端接口对接文档.md",
        "docs/develop/runner流式后端接口对接文档.md",
        "docs/develop/软件需求文档.md",
        "docs/srs/AUT中文需求输入.md",
    ]

    for doc_name in required_docs:
        assert (PROJECT_ROOT / doc_name).exists(), f"Missing shared document: {doc_name}"


def test_backend_contract_document_covers_current_pipeline_endpoints():
    content = (PROJECT_ROOT / "docs" / "develop" / "后端接口对接文档.md").read_text(encoding="utf-8")

    for endpoint in [
        "/ingest",
        "/ingest/file",
        "/parse",
        "/risk",
        "/coverage",
        "/strategy",
        "/generate",
        "/fsm",
        "/oracle",
        "/revisions",
        "/regenerate",
        "/analysis",
        "/optimize",
        "/export",
    ]:
        assert endpoint in content


def test_readme_is_chinese_tool_overview_without_external_only_context():
    content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "# AutoTestDesign" in content
    assert "智能化辅助工具" in content
    assert "核心能力" in content
    assert "工作流程" in content
    assert "技术架构" in content
    assert "CI/CD" in content

    forbidden_text = ["LibraryManagementSystem", "localDocs", "待测", "被测"]
    for text in forbidden_text:
        assert text not in content


def test_local_only_directories_are_not_tracked_by_static_artifact_suite():
    result = subprocess.run(
        ["git", "ls-files", "localDocs", "external", "temp", ".codex", ".run"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_forbidden = [line for line in result.stdout.splitlines() if line.strip()]

    assert not tracked_forbidden


def test_ragas_golden_qa_draft_has_valid_schema_and_traceability_format():
    samples = json.loads((ROOT / "tests" / "data" / "ragas_golden_qa_draft.json").read_text(encoding="utf-8"))

    required_fields = {"id", "requirement_id", "question", "answer", "ground_truth", "contexts", "source"}
    sample_ids = [item["id"] for item in samples]

    assert len(samples) >= 15
    assert len(sample_ids) == len(set(sample_ids))

    for sample in samples:
        assert required_fields.issubset(sample)
        assert sample["id"].startswith("RAGAS-AUT-")
        assert sample["requirement_id"].startswith("REQ-AUT-")
        assert sample["question"].strip()
        assert sample["answer"].strip()
        assert sample["ground_truth"].strip()
        assert isinstance(sample["contexts"], list)
        assert sample["contexts"]
        assert all(str(context).strip() for context in sample["contexts"])
        assert sample["source"] in {
            "Testing/tests/export/autotest_export (2).json::export_bundle.requirements",
            "localDocs/AUT-test/result/export/autotest_export (2).json::export_bundle.requirements",
        }
