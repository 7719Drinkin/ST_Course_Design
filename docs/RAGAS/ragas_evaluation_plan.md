# RAGAS Evaluation Plan

本文档定义 B 负责的 RAGAS 评估流程。当前实现由 D 协助完成测试脚本和可复现 runner，但文档口径仍归入 B 的 RAG / Prompt / RAGAS 工作。

## 1. Dataset

Golden QA:

```text
Testing/tests/data/ragas_golden_qa_draft.json
```

Current size:

```text
16 samples
```

Each sample contains:

- `id`
- `requirement_id`
- `question`
- `answer`
- `ground_truth`
- `contexts`
- `source`

## 2. Implemented Runner

RAGAS runner:

```text
Testing/scripts/run_ragas_evaluation.py
```

The runner performs:

1. Load golden QA.
2. Build a local retrieval corpus from AUT SRS, raw AUT requirements, exported design artifacts, and pytest files.
3. Retrieve top-k contexts for each question.
4. Generate candidate answers using DeepSeek `deepseek-v4-flash`.
5. Run RAGAS metrics.
6. Write `ragas_candidates.json`, `ragas_report.json`, and `ragas_report.md` when the output directory is writable.

## 3. Metrics

| Metric | Purpose | Current Threshold |
|---|---|---:|
| `faithfulness` | Response is supported by retrieved contexts | 0.75 |
| `answer_relevancy` | Response is relevant to the question | 0.70 |
| `llm_context_precision_with_reference` | Retrieved contexts are relevant to the reference answer | 0.65 |
| `context_recall` | Retrieved contexts cover reference facts | 0.65 |

## 4. Compatibility Handling

Current installed versions include `ragas==0.4.3` and `langchain-community==0.4.2`. RAGAS imports `langchain_community.chat_models.vertexai` even though this project does not use VertexAI. The runner injects a small import-time compatibility shim before importing RAGAS.

DeepSeek does not support `n > 1`, so `ResponseRelevancy` is configured with `strictness=1`.

Embedding for answer relevancy uses local `sentence-transformers` with `BAAI/bge-small-zh-v1.5` by default. If it cannot be loaded, the runner falls back to deterministic hash embeddings.

## 5. Commands

CI-safe checks without live LLM:

```bash
python -m pytest Testing\tests\test_ragas_evaluation.py -m "not ragas and not llm" -q -p no:cacheprovider
```

Real RAGAS smoke test:

```powershell
$env:RAGAS_SMOKE_SAMPLE_LIMIT='1'
python -m pytest Testing\tests\test_ragas_evaluation.py -m "ragas and llm" -q -p no:cacheprovider
```

Full runner:

```bash
python Testing\scripts\run_ragas_evaluation.py --top-k 3 --output-dir Testing\reports
```

If the current Python process cannot write to `Testing\reports`, use a writable temp directory and copy the report into the final document evidence manually.

## 6. Current Smoke Result

The current one-sample real RAGAS smoke run completed successfully:

| Metric | Score |
|---|---:|
| `answer_relevancy` | 0.813 |
| `context_recall` | 1.000 |
| `faithfulness` | 1.000 |
| `llm_context_precision_with_reference` | 1.000 |

Gate:

```text
PASS
```

Report output generated in the current run:

```text
C:\Users\Drink\AppData\Local\Temp\ST_Course_Design_docx_filled_20260602\ragas_candidates.json
C:\Users\Drink\AppData\Local\Temp\ST_Course_Design_docx_filled_20260602\ragas_report.json
C:\Users\Drink\AppData\Local\Temp\ST_Course_Design_docx_filled_20260602\ragas_report.md
```

## 7. Documentation Rule

For the final report, write:

```text
B implemented the RAGAS evaluation workflow with D's assistance. The evaluation uses a golden QA set, reproducible retrieved contexts, DeepSeek-generated candidate answers, and RAGAS metrics including faithfulness, answer relevancy, context precision, and context recall.
```

If only the smoke result is used, explicitly state that the result is a smoke evaluation. A full 16-sample run should be used before claiming final RAGAS benchmark quality.

