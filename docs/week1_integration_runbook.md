# Week1 Integration Runbook

本文档定义 Day6-Day7 的 Week1 Integration Run 0。它允许 D 在 A/B/E 还没有完整 UI 或最终后端时，先用最小链路或文件输出完成集成验收。

## 1. Goal

验证以下链路至少能以接口或文件形式闭环：

```text
AUT SRS / 15-sample requirements
-> ingest / local loader
-> parse output
-> EP/BVA generated test cases
-> export JSON/CSV
-> D contract checks
```

## 2. Inputs

| Input | Owner | Required by Day |
|---|---|---|
| `tests/data/aut_15_requirements.json` | D | Ready |
| parse output for 15 samples | B | Day4 |
| EP/BVA generated cases | E/B | Day6-Day7 |
| export JSON/CSV/XLSX sample | A/E | Day6-Day7 |
| UI mock or screenshot | C | Day7 optional |

## 3. Generated Test Case Contract

Each generated test case must include:

```json
{
  "test_id": "TC-AUT-008-001",
  "requirement_id": "REQ-AUT-008",
  "coverage_item_id": "COV-AUT-BORROW-001",
  "technique": "BVA",
  "title": "Borrow available book at lower valid boundary",
  "preconditions": ["Book exists", "Member exists"],
  "input_data": {
    "availableCopies": 1
  },
  "test_steps": ["POST /api/borrow"],
  "expected_result": "201 Created and availableCopies decreases by 1",
  "risk_level": "High",
  "standard_ref": "ISO/IEC/IEEE 29119-4 boundary value analysis"
}
```

## 4. Contract Checks

D checks:

| Check | Pass Condition |
|---|---|
| JSON parse | File is valid JSON |
| requirement trace | Every test case has `requirement_id` |
| coverage trace | Every test case has `coverage_item_id` |
| technique | Technique is one of EP / BVA / DT / FSM |
| expected result | Non-empty `expected_result` |
| standard reference | Non-empty `standard_ref` |
| high priority coverage | High-priority Borrowing/Return requirements have at least one generated case |
| export parse | Exported JSON/CSV/XLSX can be opened and fields match contract |

## 5. Run Procedure

1. Pull latest feature branches or collect output files from A/B/E.
2. Confirm CI-safe tests pass:

```bash
pytest -m "not aut_api and not ragas and not llm" -q
```

3. If AUT is running, run:

```bash
pytest -m aut_api -q
```

4. Validate B parse output using:

```bash
python scripts/evaluate_fr1_parse.py <b_parse_output.json>
```

5. Validate generated test cases manually or with a later contract checker.
6. Record failures in bug list format.

## 6. Bug List Format

| ID | Owner | Severity | Area | Reproduction | Expected | Actual | Due |
|---|---|---|---|---|---|---|---|
| BUG-W1-001 | B | High | FR1 parse | Run evaluator on `REQ-AUT-008` | Extract all four fields | Missing `conditions` | Day6 |

Severity:

- High: blocks Day7 gate or report evidence.
- Medium: workaround exists but must be fixed.
- Low: cosmetic or documentation issue.

## 7. Gate Result Format

```text
Week1 Integration Run 0

Status: PASS / PARTIAL / FAIL / BLOCKED

Passed:
- ...

Failed:
- ...

Blocked:
- Owner:
- Missing input:
- Impact:

Next actions:
- ...
```
