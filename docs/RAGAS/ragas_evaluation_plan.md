# RAGAS Evaluation Plan

本文档定义 Day5 及之后的 RAGAS 真实评价流程。

## 1. Current Dataset

Golden QA draft:

```text
tests/data/ragas_golden_qa_draft.json
```

Current size:

```text
8 samples
```

Each sample contains:

- `id`
- `requirement_id`
- `question`
- `answer`
- `ground_truth`
- `contexts`
- `source`

## 2. Required Input From B

B 需要提供 RAG pipeline 的真实输出。建议文件格式：

```json
[
  {
    "id": "RAGAS-AUT-004",
    "requirement_id": "REQ-AUT-008",
    "question": "What should happen when an existing member borrows an existing book with available copies?",
    "answer": "The API returns 201 Created and creates a borrowing record...",
    "contexts": [
      "FR-AUT-BORROW-002 Borrow Available Book..."
    ],
    "retrieved_context_ids": ["AUT-SRS-001#FR-AUT-BORROW-002"],
    "model_name": "gpt-or-compatible-model"
  }
]
```

D 会把 B 的 `answer` 和 `contexts` 与 golden QA 的 `ground_truth` 对齐后运行 RAGAS。

## 3. Metrics

最低要求：

| Metric | Purpose |
|---|---|
| answer relevancy | 回答是否直接回答问题 |
| faithfulness | 回答是否被 contexts 支持 |
| context precision | 检索上下文是否相关 |
| context recall | ground truth 所需信息是否被检索到 |

目标 gate：

```text
Faithfulness > 0.85
Hallucination rate < 5%
```

Hallucination rate 可由低 faithfulness 或人工标注 bad cases 估算。

## 4. Pytest Marker

RAGAS 测试必须使用：

```python
@pytest.mark.ragas
```

无 RAGAS 输入或无模型凭据时，不应影响基础 CI：

```bash
pytest -m "not aut_api and not ragas and not llm" -q
```

## 5. Report Format

```text
RAGAS Evaluation Report

Dataset:
- Golden QA: tests/data/ragas_golden_qa_draft.json
- Candidate output: <path>

Metrics:
| Metric | Score | Pass |
|---|---:|---|

Bad Cases:
| Sample | Requirement | Question | Issue | Owner |
|---|---|---|---|---|

Conclusion:
- PASS / FAIL / BLOCKED
```

## 6. Blocker Rule

如果 B 尚未提供 RAG output，D 记录：

```text
Status: BLOCKED
Owner: B
Missing input: RAG answers and retrieved contexts
Impact: RAGAS baseline cannot be computed
```
