"""RAGAS evaluation tests for AutoTestDesign RAG evidence."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from scripts.run_ragas_evaluation import (
    DEFAULT_RAGAS_THRESHOLDS,
    _passes_gate,
    _score_health,
    build_candidate_rows,
    build_corpus,
    install_ragas_vertexai_compat,
    load_golden_samples,
    load_local_env,
    retrieve_contexts,
    run_ragas_evaluation,
)


ROOT = Path(__file__).resolve().parents[3]
GOLDEN_QA = ROOT / "Testing" / "tests" / "data" / "ragas_golden_qa_draft.json"
TRACKED_EXPORT = ROOT / "Testing" / "tests" / "export" / "autotest_export (2).json"
LOCAL_EXPORT = ROOT / "localDocs" / "AUT-test" / "result" / "export" / "autotest_export (2).json"


def test_ragas_golden_qa_dataset_contract():
    samples = load_golden_samples(GOLDEN_QA)

    assert len(samples) >= 15
    seen_ids = set()
    for sample in samples:
        assert sample["id"].startswith("RAGAS-AUT-")
        assert sample["id"] not in seen_ids
        seen_ids.add(sample["id"])
        assert re.fullmatch(r"REQ-AUT-\d{3}", sample["requirement_id"])
        assert sample["question"].strip()
        assert sample["answer"].strip()
        assert sample["ground_truth"].strip()
        assert sample["contexts"]
        assert all(str(context).strip() for context in sample["contexts"])
        assert sample["source"].strip()


def test_ragas_local_retrieval_produces_contexts_for_each_sample():
    _skip_without_local_export()

    corpus = build_corpus()
    samples = load_golden_samples(GOLDEN_QA)

    assert len(corpus) >= 20
    for sample in samples:
        contexts = retrieve_contexts(sample, corpus, top_k=4)
        assert contexts
        assert len(contexts) <= 4
        query_terms = {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9_/-]+", f"{sample['question']} {sample['ground_truth']}")
            if len(token) > 2
        }
        context_terms = {
            token.lower()
            for context in contexts
            for token in re.findall(r"[A-Za-z0-9_/-]+", context)
            if len(token) > 2
        }
        assert len(query_terms & context_terms) >= 3


def test_ragas_retrieval_corpus_excludes_evaluation_plan_leakage():
    _skip_without_local_export()

    corpus = build_corpus()
    sources = {chunk.source for chunk in corpus}

    assert "docs/RAGAS/ragas_evaluation_plan.md" not in sources
    assert "localDocs/RAGAS真实评估实施方案.md" not in sources
    assert sources == {_expected_export_source()}

    malformed_sample = next(sample for sample in load_golden_samples(GOLDEN_QA) if sample["id"] == "RAGAS-AUT-016")
    contexts = retrieve_contexts(malformed_sample, corpus, top_k=3)
    combined = "\n".join(contexts).lower()
    assert "malformed json" in combined
    assert "rejects malformed json requests" in combined


def test_ragas_candidate_rows_match_required_schema_without_llm():
    _skip_without_local_export()

    samples = load_golden_samples(GOLDEN_QA)[:3]
    rows = build_candidate_rows(samples, use_deepseek=False, allow_reference_fallback=True, top_k=3)

    for row in rows:
        assert set(row) == {
            "id",
            "requirement_id",
            "user_input",
            "response",
            "reference",
            "retrieved_contexts",
        }
        assert row["user_input"]
        assert row["response"]
        assert row["reference"]
        assert row["retrieved_contexts"]


def test_ragas_gate_rejects_missing_or_critical_scores():
    healthy_summary = {metric: threshold + 0.1 for metric, threshold in DEFAULT_RAGAS_THRESHOLDS.items()}
    missing_metric_summary = dict(healthy_summary)
    missing_metric_summary.pop("faithfulness")

    assert not _passes_gate(missing_metric_summary, {"invalid_score_count": 0, "critical_failure_count": 0})

    rows = [
        {
            "id": "RAGAS-AUT-X",
            "requirement_id": "REQ-AUT-999",
            "faithfulness": 1.0,
            "context_recall": 0.0,
            "llm_context_precision_with_reference": 1.0,
            "answer_relevancy": 1.0,
        }
    ]
    health = _score_health(rows)
    assert health["critical_failure_count"] == 1
    assert not _passes_gate(healthy_summary, health)


def test_installed_ragas_imports_with_compatibility_shim():
    install_ragas_vertexai_compat()

    from ragas import evaluate
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    assert callable(evaluate)
    assert Faithfulness().name == "faithfulness"
    assert LLMContextPrecisionWithReference().name == "llm_context_precision_with_reference"
    assert LLMContextRecall().name == "context_recall"
    assert ResponseRelevancy().name == "answer_relevancy"


@pytest.mark.ragas
@pytest.mark.llm
def test_real_ragas_evaluation_smoke():
    load_local_env()
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is required for real RAGAS smoke evaluation.")
    _skip_without_local_export()

    sample_limit = int(os.getenv("RAGAS_SMOKE_SAMPLE_LIMIT", "1"))
    output_dir = ROOT / "Testing" / "reports"
    report = run_ragas_evaluation(
        sample_limit=sample_limit,
        output_dir=output_dir,
        top_k=3,
        report_prefix="ragas_smoke",
    )

    assert report["sample_count"] == sample_limit
    assert report["summary"]
    assert set(report["thresholds"]) == set(DEFAULT_RAGAS_THRESHOLDS)
    assert "output_files" in report or "output_write_error" in report


def _skip_without_local_export() -> None:
    if not (TRACKED_EXPORT.exists() or LOCAL_EXPORT.exists()):
        pytest.skip(
            "Export bundle is required for this RAGAS evidence test. "
            f"Expected {TRACKED_EXPORT} or {LOCAL_EXPORT}."
        )


def _expected_export_source() -> str:
    if TRACKED_EXPORT.exists():
        return "Testing/tests/export/autotest_export (2).json::export_bundle.requirements"
    return "localDocs/AUT-test/result/export/autotest_export (2).json::export_bundle.requirements"
