# FR1 Parse Evaluation Plan

本文档定义 D 对 B 的 FR1.1 requirement parsing 输出进行评分的标准、输入格式和报告格式。

## 1. Evaluation Target

FR1.1 目标是从 AUT requirement 中抽取四类关键字段：

1. `input_fields`
2. `data_ranges`
3. `conditions`
4. `expected_action`

评价基准来自：

```text
tests/data/aut_15_requirements.json
```

## 2. Candidate Output Format

B 需要提供一个 JSON array：

```json
[
  {
    "requirement_id": "REQ-AUT-008",
    "input_fields": ["book.id", "member.id", "availableCopies"],
    "data_ranges": ["availableCopies: integer > 0"],
    "conditions": ["Book exists", "Member exists", "availableCopies > 0"],
    "expected_action": "Return 201, create a borrowing record, set borrowDate and dueDate, and decrement availableCopies by 1.",
    "confidence": 0.85,
    "source_context_ids": ["AUT-SRS-001#FR-AUT-BORROW-002"]
  }
]
```

Required fields:

| Field | Required |
|---|---:|
| `requirement_id` | yes |
| `input_fields` | yes |
| `data_ranges` | yes |
| `conditions` | yes |
| `expected_action` | yes |

Optional but useful:

| Field | Purpose |
|---|---|
| `confidence` | 支持后续 Oracle / review |
| `source_context_ids` | 支持 RAG 追溯 |
| `prompt_template_id` | 支持 Prompt 透明化 |

## 3. Scoring Rule

基础自动评分：

| Field Type | Score |
|---|---:|
| Correct / semantically matched | 1 |
| Missing or unrelated | 0 |

人工复核可使用 0.5：

| Field Type | Score |
|---|---:|
| Partially correct but missing important terms | 0.5 |

总分：

```text
total_score = sum(field_score)
max_score = 15 requirements * 4 fields = 60
overall_accuracy = total_score / max_score
```

Pass condition:

```text
overall_accuracy >= 80%
```

## 4. Field-Level Expectations

### input_fields

应抽取 endpoint 输入、path parameter、body field 或业务关键字段。

Example:

```text
REQ-AUT-008 -> book.id, member.id, availableCopies
```

### data_ranges

应抽取数据类型、边界、值域或合法/非法取值。

Example:

```text
availableCopies: integer > 0
```

### conditions

应抽取前置条件、决策表条件或状态迁移 guard。

Example:

```text
Book exists; Member exists; availableCopies > 0
```

### expected_action

应抽取可断言的系统行为。

Example:

```text
Return 201; create borrowing record; set borrowDate and dueDate; decrement availableCopies by 1
```

## 5. Evaluation Command

当 B 提供 parse output 后执行：

```bash
python scripts/evaluate_fr1_parse.py path/to/b_parse_output.json
```

可保存 JSON 报告：

```bash
python scripts/evaluate_fr1_parse.py path/to/b_parse_output.json --output localDocs/fr1_quality_report.json
```

## 6. Report Template

```text
FR1 Quality Report

Input:
- Expected: tests/data/aut_15_requirements.json
- Candidate: <path>

Result:
- Overall accuracy:
- input_fields accuracy:
- data_ranges accuracy:
- conditions accuracy:
- expected_action accuracy:

Bad cases:
| Requirement | Field | Expected | Actual | Score | Comment |
|---|---|---|---|---:|---|

Conclusion:
- PASS / FAIL
- Required prompt changes:
```

## 7. Blocker Rule

如果 B 在 Day4 尚未提供 parse output，D 不填写虚假准确率，只记录：

```text
Status: BLOCKED
Owner: B
Missing input: 15-sample parse output
Impact: FR1 Quality Gate cannot be completed
```
