"""RAGAS evaluation tests for AutoTestDesign RAG evidence."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from scripts.run_ragas_evaluation import (
    DEFAULT_RAGAS_THRESHOLDS,
    build_candidate_rows,
    build_corpus,
    install_ragas_vertexai_compat,
    load_golden_samples,
    load_local_env,
    retrieve_contexts,
    run_ragas_evaluation,
)


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_QA = ROOT / "Testing" / "tests" / "data" / "ragas_golden_qa_draft.json"


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


def test_ragas_candidate_rows_match_required_schema_without_llm():
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

    sample_limit = int(os.getenv("RAGAS_SMOKE_SAMPLE_LIMIT", "1"))
    output_dir = ROOT / "Testing" / "reports"
    report = run_ragas_evaluation(sample_limit=sample_limit, output_dir=output_dir, top_k=3)

    assert report["sample_count"] == sample_limit
    assert report["summary"]
    assert set(report["thresholds"]) == set(DEFAULT_RAGAS_THRESHOLDS)
    assert "output_files" in report or "output_write_error" in report
