"""Static checks that can run in CI without the live AUT service."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_aut_srs_ieee830_exists_and_contains_required_sections():
    srs_path = ROOT / "docs" / "AUT_SRS_IEEE830_v1.md"

    assert srs_path.exists()
    content = srs_path.read_text(encoding="utf-8")
    for heading in [
        "# Software Requirements Specification",
        "## 1. Introduction",
        "## 2. Overall Description",
        "## 3. Specific Requirements",
        "## 4. Data Requirements",
        "## 5. Non-Functional Requirements",
        "## 6. Known Limitations",
    ]:
        assert heading in content


def test_aut_srs_covers_required_aut_modules():
    content = (ROOT / "docs" / "AUT_SRS_IEEE830_v1.md").read_text(encoding="utf-8")

    for requirement_id in [
        "FR-AUT-BOOK-001",
        "FR-AUT-MEMBER-001",
        "FR-AUT-BORROW-002",
        "FR-AUT-RETURN-001",
    ]:
        assert requirement_id in content


def test_15_requirement_samples_are_present_and_unique():
    requirements_path = ROOT / "tests" / "data" / "aut_15_requirements.json"
    requirements = json.loads(requirements_path.read_text(encoding="utf-8"))

    ids = [item["id"] for item in requirements]
    assert len(requirements) == 15
    assert len(ids) == len(set(ids))


def test_15_requirement_samples_cover_teacher_required_techniques():
    requirements = json.loads((ROOT / "tests" / "data" / "aut_15_requirements.json").read_text(encoding="utf-8"))
    techniques = {technique for item in requirements for technique in item["techniques"]}
    areas = {item["area"] for item in requirements}

    assert {"EP", "BVA", "DT", "FSM"}.issubset(techniques)
    assert {"Book CRUD", "Member CRUD", "Borrowing", "Return", "Records", "Error Handling"}.issubset(areas)


def test_day3_day7_shared_documents_exist():
    required_docs = [
        "fr1_parse_evaluation_plan.md",
        "testing_framework_rationale.md",
        "ragas_evaluation_plan.md",
        "risk_mitigation_strategy_draft.md",
        "week1_integration_runbook.md",
        "day7_document_qa_checklist.md",
        "integration_interfaces.md",
        "branch_policy.md",
    ]

    for doc_name in required_docs:
        assert (ROOT / "docs" / doc_name).exists()


def test_integration_interface_document_covers_day3_day7_contracts():
    content = (ROOT / "docs" / "integration_interfaces.md").read_text(encoding="utf-8")

    for required_text in [
        "# Integration Interfaces for Day3-Day7",
        "coverage_item_id",
        "revision_id",
        "Interactive Review",
        "Prompt Transparency",
        "A 后端接口预留",
        "B RAG / LLM 输出接口预留",
        "E 测试生成器输出接口预留",
        "C 前端展示接口预留",
        "D 验收规则",
    ]:
        assert required_text in content


def test_ragas_golden_qa_draft_has_valid_schema_and_traceability():
    requirements = json.loads((ROOT / "tests" / "data" / "aut_15_requirements.json").read_text(encoding="utf-8"))
    requirement_ids = {item["id"] for item in requirements}
    samples = json.loads((ROOT / "tests" / "data" / "ragas_golden_qa_draft.json").read_text(encoding="utf-8"))

    required_fields = {"id", "requirement_id", "question", "answer", "ground_truth", "contexts", "source"}
    sample_ids = [item["id"] for item in samples]

    assert len(samples) >= 6
    assert len(sample_ids) == len(set(sample_ids))

    for sample in samples:
        assert required_fields.issubset(sample)
        assert sample["requirement_id"] in requirement_ids
        assert sample["question"]
        assert sample["answer"]
        assert sample["ground_truth"]
        assert isinstance(sample["contexts"], list)
        assert sample["contexts"]


def test_day3_day7_templates_have_required_traceability_fields():
    fr1_template = json.loads((ROOT / "tests" / "data" / "fr1_parse_output_template.json").read_text(encoding="utf-8"))
    generated_template = json.loads(
        (ROOT / "tests" / "data" / "generated_test_cases_template.json").read_text(encoding="utf-8")
    )

    assert {"requirement_id", "input_fields", "data_ranges", "conditions", "expected_action"}.issubset(fr1_template[0])
    assert {
        "test_id",
        "requirement_id",
        "coverage_item_id",
        "technique",
        "expected_result",
        "standard_ref",
    }.issubset(generated_template[0])
