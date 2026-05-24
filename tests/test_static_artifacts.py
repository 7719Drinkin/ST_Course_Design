"""Static checks that can run in CI without the live AUT service."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _first_existing(*relative_paths: str) -> Path:
    for relative_path in relative_paths:
        candidate = ROOT / relative_path
        if candidate.exists():
            return candidate
    raise AssertionError(f"None of these paths exist: {relative_paths}")


def test_aut_srs_ieee830_exists_and_contains_required_sections():
    srs_path = _first_existing("docs/srs/AUT_SRS_IEEE830_v1.md", "docs/AUT_SRS_IEEE830_v1.md")

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
    srs_path = _first_existing("docs/srs/AUT_SRS_IEEE830_v1.md", "docs/AUT_SRS_IEEE830_v1.md")
    content = srs_path.read_text(encoding="utf-8")

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


def test_shared_documents_exist():
    required_docs = [
        "branch_policy.md",
        "小组分工_更新版.md",
        "srs/AUT_SRS_IEEE830_v1.md",
        "srs/fr1_parse_evaluation_plan.md",
        "test/testing_framework_rationale.md",
        "RAGAS/ragas_evaluation_plan.md",
    ]

    for doc_name in required_docs:
        assert (ROOT / "docs" / doc_name).exists()


def test_role_boundary_document_covers_cross_role_contracts():
    content = (ROOT / "docs" / "小组分工_更新版.md").read_text(encoding="utf-8")

    for required_text in [
        "# 小组分工（功能边界版）",
        "交互式测试设计强制链路",
        "多源需求输入与归一化",
        "需求结构化解析",
        "风险评分与测试优先级",
        "概念",
        "覆盖项识别",
        "覆盖策略与方法",
        "测试用例及其设计的可追溯性",
        "提示设计",
        "结果分析",
        "基于证据的改进",
        "输出与导出",
        "NFR（非功能需求）保障",
        "接口边界总览",
        "/ingest",
        "/parse",
        "/risk",
        "/coverage",
        "/strategy",
        "/generate",
        "/fsm",
        "/revisions",
        "/regenerate",
        "/analysis",
        "/export",
        "coverage_item_id",
        "revision_id",
        "设计者",
        "F11 交互式审查与修订",
        "F14 基于证据的改进",
        "A — 后端与接口负责人",
        "B — RAG（检索增强生成）、LLM（大语言模型）与 Prompt（提示词）负责人",
        "C — 前端交互与设计者参与负责人",
        "D — 测试、集成与文档证据负责人",
        "E — 测试设计算法负责人",
        "功能点对接总表",
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
