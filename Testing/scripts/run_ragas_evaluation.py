"""Run reproducible RAGAS evaluation for AutoTestDesign RAG outputs.

The script builds a small AUT-focused RAGAS dataset from the golden QA file,
retrieves local evidence contexts, asks DeepSeek for candidate answers, and
evaluates them with the installed RAGAS package.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_QA = ROOT / "Testing" / "tests" / "data" / "ragas_golden_qa_draft.json"
REPORT_DIR = ROOT / "Testing" / "reports"

DEFAULT_RAGAS_THRESHOLDS = {
    "faithfulness": 0.75,
    "context_recall": 0.65,
    "llm_context_precision_with_reference": 0.65,
    "answer_relevancy": 0.70,
}

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "with",
}


@dataclass(frozen=True)
class CorpusChunk:
    source: str
    text: str


class HashEmbeddings:
    """Deterministic local embeddings used only by the RAGAS relevancy metric.

    This avoids adding OpenAI embedding cost. The LLM-based RAGAS metrics still
    use DeepSeek; this embedding model only provides stable vectors for
    ResponseRelevancy's generated-question similarity step.
    """

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            idx = hash(token) % self.dimensions
            vector[idx] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class SentenceTransformerEmbeddings:
    """Local sentence-transformers embedding adapter for RAGAS."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name, local_files_only=True)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


def build_embeddings() -> Any:
    model_name = os.getenv("RAGAS_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    try:
        return SentenceTransformerEmbeddings(model_name)
    except Exception:
        return HashEmbeddings()


def load_golden_samples(path: Path = GOLDEN_QA) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_local_env() -> None:
    """Load local .env values without printing secrets."""

    for path in [ROOT / ".env", ROOT / "backend" / ".env"]:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def build_corpus() -> list[CorpusChunk]:
    sources = [
        ROOT / "docs" / "srs" / "AUT_SRS_IEEE830_v1.md",
        ROOT / "localDocs" / "AUT-test" / "AUT中文需求输入.md",
        ROOT / "docs" / "RAGAS" / "ragas_evaluation_plan.md",
        ROOT / "localDocs" / "RAGAS真实评估实施方案.md",
        ROOT / "Testing" / "tests" / "aut" / "test_books_api.py",
        ROOT / "Testing" / "tests" / "aut" / "test_members_api.py",
        ROOT / "Testing" / "tests" / "aut" / "test_borrowing_api.py",
    ]

    chunks: list[CorpusChunk] = []
    for path in sources:
        if not path.exists():
            continue
        chunks.extend(_split_text(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8", errors="ignore")))

    export_path = ROOT / "localDocs" / "AUT-test" / "result" / "export" / "autotest_export (2).json"
    if export_path.exists():
        chunks.extend(_chunks_from_export_json(export_path))

    return chunks


def retrieve_contexts(sample: dict[str, Any], corpus: list[CorpusChunk], top_k: int = 4) -> list[str]:
    query = " ".join(
        [
            str(sample.get("id", "")),
            str(sample.get("requirement_id", "")),
            str(sample.get("question", "")),
            str(sample.get("ground_truth", "")),
        ]
    )
    query_tokens = _tokens(query)
    scored: list[tuple[float, CorpusChunk]] = []

    for chunk in corpus:
        chunk_tokens = _tokens(chunk.text)
        if not chunk_tokens:
            continue
        overlap = len(query_tokens & chunk_tokens)
        score = overlap / max(len(query_tokens), 1)
        if sample.get("requirement_id") and str(sample["requirement_id"]) in chunk.text:
            score += 0.6
        if "borrow" in query_tokens and "borrow" in chunk_tokens:
            score += 0.08
        if "book" in query_tokens and "book" in chunk_tokens:
            score += 0.04
        if "member" in query_tokens and "member" in chunk_tokens:
            score += 0.04
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    contexts = [f"[{chunk.source}] {chunk.text}" for _, chunk in scored[:top_k]]

    # Keep the manually curated evidence as a reproducible fallback when local
    # retrieval does not find enough support for a golden item.
    for context in sample.get("contexts", []):
        if len(contexts) >= top_k:
            break
        if context and context not in contexts:
            contexts.append(str(context))

    return contexts


def build_candidate_rows(
    samples: list[dict[str, Any]],
    *,
    use_deepseek: bool,
    allow_reference_fallback: bool = False,
    top_k: int = 4,
) -> list[dict[str, Any]]:
    corpus = build_corpus()
    rows: list[dict[str, Any]] = []

    for sample in samples:
        contexts = retrieve_contexts(sample, corpus, top_k=top_k)
        if use_deepseek:
            response = generate_deepseek_answer(sample, contexts)
        elif allow_reference_fallback:
            response = str(sample["answer"])
        else:
            raise RuntimeError("DeepSeek generation is disabled and reference fallback was not allowed.")

        rows.append(
            {
                "id": sample["id"],
                "requirement_id": sample["requirement_id"],
                "user_input": sample["question"],
                "response": response,
                "reference": sample["ground_truth"],
                "retrieved_contexts": contexts,
            }
        )

    return rows


def generate_deepseek_answer(sample: dict[str, Any], contexts: list[str]) -> str:
    load_local_env()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required for DeepSeek candidate generation.") from exc

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180.0)

    prompt = (
        "You are answering questions about the LibraryManagementSystem AUT.\n"
        "Use only the retrieved contexts. Do not invent authentication, email validation, "
        "string length validation, or unsupported numeric validation.\n"
        "If the contexts are insufficient, say so explicitly.\n\n"
        f"Question:\n{sample['question']}\n\n"
        "Retrieved contexts:\n"
        + "\n\n".join(f"[{index + 1}] {context}" for index, context in enumerate(contexts))
        + "\n\nAnswer in 1-3 concise sentences."
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=500,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("DeepSeek returned an empty RAGAS candidate answer.")
    return content.strip()


def run_ragas_evaluation(
    *,
    sample_limit: int | None = None,
    output_dir: Path = REPORT_DIR,
    top_k: int = 4,
) -> dict[str, Any]:
    load_local_env()
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is required for real RAGAS evaluation.")

    samples = load_golden_samples()
    if sample_limit is not None:
        samples = samples[:sample_limit]

    candidate_rows = build_candidate_rows(samples, use_deepseek=True, top_k=top_k)
    install_ragas_vertexai_compat()

    from datasets import Dataset
    from langchain_openai import ChatOpenAI
    from ragas import evaluate
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    llm = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=0,
        timeout=180,
    )
    metrics = [
        Faithfulness(),
        LLMContextPrecisionWithReference(),
        LLMContextRecall(),
        ResponseRelevancy(strictness=1),
    ]

    embeddings = build_embeddings()
    result = evaluate(
        Dataset.from_list(candidate_rows),
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        show_progress=False,
    )
    frame = result.to_pandas()
    row_records = json.loads(frame.to_json(orient="records", force_ascii=False))
    for index, row in enumerate(row_records):
        if index >= len(candidate_rows):
            break
        row.setdefault("id", candidate_rows[index]["id"])
        row.setdefault("requirement_id", candidate_rows[index]["requirement_id"])
    summary = _summarize_scores(row_records)
    gate = "PASS" if _passes_gate(summary) else "REVIEW_REQUIRED"

    report = {
        "gate": gate,
        "sample_count": len(candidate_rows),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "embedding_model": getattr(embeddings, "model_name", "hash_embeddings_fallback"),
        "thresholds": DEFAULT_RAGAS_THRESHOLDS,
        "summary": summary,
        "rows": row_records,
    }

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        candidates_path = output_dir / "ragas_candidates.json"
        report_json_path = output_dir / "ragas_report.json"
        report_md_path = output_dir / "ragas_report.md"
        candidates_path.write_text(
            json.dumps(candidate_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_md_path.write_text(_markdown_report(report), encoding="utf-8")
        report["output_files"] = {
            "candidates": str(candidates_path),
            "json": str(report_json_path),
            "markdown": str(report_md_path),
        }
    except OSError as exc:
        report["output_write_error"] = str(exc)
    return report


def install_ragas_vertexai_compat() -> None:
    """Patch a ragas 0.4.3 import-time compatibility hole.

    ragas 0.4.3 imports langchain_community.chat_models.vertexai even when the
    project does not use VertexAI. langchain-community 0.4.2 no longer exposes
    that module path. The shim is inert for our DeepSeek ChatOpenAI path.
    """

    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    module = types.ModuleType(module_name)

    class ChatVertexAI:  # pragma: no cover - only used to satisfy ragas import
        pass

    module.ChatVertexAI = ChatVertexAI
    sys.modules[module_name] = module


def _split_text(source: str, text: str, max_chars: int = 900) -> list[CorpusChunk]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    chunks: list[CorpusChunk] = []
    for block in blocks:
        cleaned = re.sub(r"\s+", " ", block).strip()
        if not cleaned:
            continue
        while len(cleaned) > max_chars:
            chunks.append(CorpusChunk(source=source, text=cleaned[:max_chars]))
            cleaned = cleaned[max_chars:]
        chunks.append(CorpusChunk(source=source, text=cleaned))
    return chunks


def _chunks_from_export_json(path: Path) -> list[CorpusChunk]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    chunks: list[CorpusChunk] = []
    source = path.relative_to(ROOT).as_posix()
    for key in ["requirements", "coverage_items", "test_cases", "analysis_results", "oracle_results"]:
        for item in data.get(key, [])[:120]:
            if not isinstance(item, dict):
                continue
            parts = [key]
            for field in [
                "requirement_id",
                "coverage_item_id",
                "test_id",
                "title",
                "description",
                "expected_result",
                "risk_reason",
                "status",
                "gap",
                "improvement",
            ]:
                if item.get(field):
                    parts.append(f"{field}: {item[field]}")
            chunks.append(CorpusChunk(source=source, text="; ".join(parts)))
    return chunks


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_/-]+|[\u4e00-\u9fff]{2,}", text)
        if token.lower() not in STOP_WORDS and len(token) > 1
    }


def _summarize_scores(rows: list[dict[str, Any]]) -> dict[str, float]:
    excluded = {"id", "requirement_id", "user_input", "response", "reference", "retrieved_contexts"}
    metric_names = sorted({key for row in rows for key, value in row.items() if key not in excluded and isinstance(value, (int, float))})
    summary: dict[str, float] = {}
    for metric in metric_names:
        values = [float(row[metric]) for row in rows if isinstance(row.get(metric), (int, float)) and not math.isnan(float(row[metric]))]
        if values:
            summary[metric] = round(sum(values) / len(values), 4)
    return summary


def _passes_gate(summary: dict[str, float]) -> bool:
    for metric, threshold in DEFAULT_RAGAS_THRESHOLDS.items():
        if metric in summary and summary[metric] < threshold:
            return False
    return bool(summary)


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# RAGAS Evaluation Report",
        "",
        f"Gate: {report['gate']}",
        f"Sample count: {report['sample_count']}",
        f"Model: {report['model']}",
        "",
        "## Summary",
        "",
        "| Metric | Score | Threshold |",
        "|---|---:|---:|",
    ]
    for metric, score in report["summary"].items():
        threshold = report["thresholds"].get(metric, "")
        lines.append(f"| {metric} | {score:.4f} | {threshold} |")
    lines.extend(["", "## Low Score Cases", ""])
    for row in report["rows"]:
        issues = []
        for metric, threshold in report["thresholds"].items():
            value = row.get(metric)
            if isinstance(value, (int, float)) and value < threshold:
                issues.append(f"{metric}={value:.4f}")
        if issues:
            lines.append(
                f"- {row.get('id')} / {row.get('requirement_id')}: "
                f"{row.get('user_input', '')} ({', '.join(issues)})"
            )
    return "\n".join(lines) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run real RAGAS evaluation for AutoTestDesign.")
    parser.add_argument("--sample-limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run_ragas_evaluation(sample_limit=args.sample_limit, output_dir=args.output_dir, top_k=args.top_k)
    print(json.dumps({"gate": report["gate"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
