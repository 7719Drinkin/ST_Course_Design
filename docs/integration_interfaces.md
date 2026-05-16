# Integration Interfaces for Day3-Day7

本文档定义 D 角色在 Day3-Day7 阶段需要 A/B/C/E 配合的跨成员对接接口。A/B/C/E 在各自模块完成时，应尽量按本文档字段输出，以便 D 编写集成测试、FR1 解析评估、RAGAS 评价、A/B 实验、Day7 gate report 和演示验证。

本文档不是最终 API 设计的替代品。如果 A/B/C/E 的实现需要调整字段，应在 Pull Request 中说明差异，并同步更新本文档。

## 1. 共享 ID 规则

所有跨模块数据应保留可追踪 ID。

| ID | 来源 | 用途 |
|---|---|---|
| `requirement_id` | `tests/data/aut_15_requirements.json` | 连接需求、测试设计、RAGAS、A/B 实验和报告 |
| `fr_id` | `docs/AUT_SRS_IEEE830_v1.md` | 连接 AUT SRS 的功能需求 |
| `test_id` | FR3/FR4/pytest/generated cases | 标识单个测试用例 |
| `coverage_item_id` | FR3 coverage model / Interactive Review | 标识测试用例来源覆盖项，支持差量生成与追溯 |
| `revision_id` | Interactive Review | 标识测试人员修改记录 |
| `source` | AUT SRS / requirement set / knowledge base | 标识数据来源 |
| `standard_ref` | 测试知识库/RAG | 标识测试设计标准或依据 |

推荐格式：

- `requirement_id`: `REQ-AUT-001`
- `fr_id`: `FR-AUT-BOOK-001`
- `test_id`: `TC-AUT-001`
- `coverage_item_id`: `COV-AUT-BORROW-001`
- `revision_id`: `REV-0001`

## 2. Requirement 输入结构

B 的 requirement parser、E 的测试生成器、A 的后端接口和 C 的展示 mock data 都应能处理该结构。

```json
{
  "id": "REQ-AUT-008",
  "area": "Borrowing",
  "title": "Borrow an available book",
  "raw_requirement": "The system shall create a borrowing record when an existing member borrows an existing book with availableCopies greater than 0.",
  "input_fields": ["book.id", "member.id"],
  "data_ranges": ["availableCopies: integer > 0"],
  "conditions": ["Book exists", "Member exists", "availableCopies > 0"],
  "expected_action": "Return 201, create a borrowing record, set borrowDate and dueDate, and decrement availableCopies by 1.",
  "techniques": ["DT", "FSM", "BVA"],
  "priority": "High"
}
```

字段要求：

| Field | Required | Owner | Notes |
|---|---:|---|---|
| `id` | yes | D | 需求样本 ID |
| `area` | yes | D | 业务区域，如 Book CRUD / Borrowing |
| `title` | yes | D/B | 简短标题 |
| `raw_requirement` | yes | D/B | 原始需求文本 |
| `input_fields` | yes | B/E | 解析出的输入字段 |
| `data_ranges` | yes | B/E | 值域、边界或约束 |
| `conditions` | yes | B/E | 前置条件或决策条件 |
| `expected_action` | yes | B/E | 期望系统行为 |
| `techniques` | yes | D/E | EP / BVA / DT / FSM |
| `priority` | yes | D/B | High / Medium / Low |

## 3. Day3-Day7 交付物总览

| Day | Owner | D 需要的输入 | D 的动作 |
|---|---|---|---|
| Day3 | D | 无外部依赖 | 完成测试框架说明、FR1 评价规则、接口契约更新 |
| Day4 | B | 15 条 parse output | 计算 FR1 parse accuracy，输出 bad cases |
| Day5 | B | RAG answers、retrieved contexts、risk matrix | 准备 RAGAS baseline 与 AUT 风险缓解策略 |
| Day6 | A/B/E | ingest/parse/generate/export 最小链路或文件输出 | 执行 Week1 integration run 0 |
| Day7 | B/E/C/A | EP/BVA 输出、UI/mock 状态、共享文档内容 | 执行 FR3 gate 与文档方向 QA |

## 4. A 后端接口预留

A 的后端接口实现完成前，D 先按以下 contract 准备集成测试。

### 4.1 Requirement Ingest

Endpoint:

```http
POST /ingest
```

Request:

```json
{
  "source_type": "json",
  "content": [
    {
      "id": "REQ-AUT-001",
      "raw_requirement": "The system shall return a JSON array of all books when the client sends GET /api/books."
    }
  ]
}
```

Expected response:

```json
{
  "requirements": [
    {
      "requirement_id": "REQ-AUT-001",
      "raw_requirement": "The system shall return a JSON array of all books when the client sends GET /api/books.",
      "source": "aut_15_requirements"
    }
  ],
  "errors": []
}
```

### 4.2 Requirement Parse

Endpoint:

```http
POST /parse
```

Request:

```json
{
  "requirement_id": "REQ-AUT-008",
  "raw_requirement": "The system shall create a borrowing record when an existing member borrows an existing book with availableCopies greater than 0."
}
```

Expected response:

```json
{
  "requirement_id": "REQ-AUT-008",
  "input_fields": ["book.id", "member.id", "availableCopies"],
  "data_ranges": ["availableCopies: integer > 0"],
  "conditions": ["Book exists", "Member exists", "availableCopies > 0"],
  "expected_action": "Create borrowing record and decrement availableCopies by 1",
  "confidence": 0.85,
  "missing_fields": []
}
```

### 4.3 FSM Generation

Endpoint:

```http
POST /fsm
```

Request:

```json
{
  "requirement_ids": ["REQ-AUT-008", "REQ-AUT-012", "REQ-AUT-013"]
}
```

Expected response:

```json
{
  "states": ["Available", "Borrowed", "Returned", "Rejected"],
  "transitions": [
    {
      "from": "Available",
      "to": "Borrowed",
      "event": "POST /api/borrow",
      "condition": "book exists, member exists, availableCopies > 0"
    }
  ],
  "coverage": {
    "all_states": ["Available", "Borrowed", "Returned", "Rejected"],
    "all_transitions": ["Available->Borrowed", "Borrowed->Returned"]
  },
  "mermaid": "stateDiagram-v2\n    Available --> Borrowed: POST /api/borrow"
}
```

### 4.4 Export

Endpoints:

```http
GET /export/json
GET /export/csv
GET /export/xlsx
```

Exported test cases should include at least:

| Field | Required |
|---|---:|
| `test_id` | yes |
| `requirement_id` | yes |
| `technique` | yes |
| `preconditions` | yes |
| `test_steps` | yes |
| `expected_result` | yes |
| `risk_level` | yes |
| `standard_ref` | yes |

### 4.5 Interactive Review Minimal Contract

Interactive Review 在 Day7 前不要求完整实现，但 A/C/E 应预留以下数据结构，避免 Day10 返工。

Design session:

```json
{
  "session_id": "DS-AUT-001",
  "requirement_ids": ["REQ-AUT-008", "REQ-AUT-009"],
  "created_at": "2026-05-16T10:00:00Z",
  "status": "draft"
}
```

Revision record:

```json
{
  "revision_id": "REV-0001",
  "session_id": "DS-AUT-001",
  "target_type": "coverage_item",
  "target_id": "COV-AUT-BORROW-001",
  "operation": "update",
  "before": {
    "condition": "availableCopies > 0"
  },
  "after": {
    "condition": "book exists AND member exists AND availableCopies > 0"
  },
  "reason": "Tester refined the coverage condition",
  "created_by": "tester",
  "created_at": "2026-05-16T10:05:00Z"
}
```

Regeneration request:

```json
{
  "session_id": "DS-AUT-001",
  "revision_id": "REV-0001",
  "affected_coverage_item_ids": ["COV-AUT-BORROW-001"],
  "mode": "incremental"
}
```

## 5. B RAG / LLM 输出接口预留

### 5.1 Parse Output

B 的 parser 输出应至少覆盖 FR 1.1 的四个关键字段：

```json
{
  "requirement_id": "REQ-AUT-008",
  "input_fields": ["book.id", "member.id", "availableCopies"],
  "data_ranges": ["availableCopies: integer > 0"],
  "conditions": ["Book exists", "Member exists", "availableCopies > 0"],
  "expected_action": "Return 201 and create a borrowing record",
  "confidence": 0.85,
  "source_context_ids": ["AUT_SRS:FR-AUT-BORROW-002"]
}
```

### 5.2 Prompt Transparency

B 的 RAG / LLM 输出应保留 Prompt 透明度字段，供 C 展示和 D 追溯。

```json
{
  "requirement_id": "REQ-AUT-008",
  "prompt_template_id": "PROMPT-FR1-V1",
  "prompt_inputs": {
    "raw_requirement": "The system shall create a borrowing record..."
  },
  "retrieved_context_ids": ["AUT-SRS-001#FR-AUT-BORROW-002"],
  "model_name": "gpt-or-compatible-model",
  "output_schema_version": "parse-v1"
}
```

### 5.3 RAGAS Evaluation Sample

RAGAS 样本应使用以下结构：

```json
{
  "id": "RAGAS-AUT-001",
  "requirement_id": "REQ-AUT-008",
  "question": "What should happen when an existing member borrows an existing book with available copies?",
  "answer": "The API should return 201, create a borrowing record, set borrowDate and dueDate, and decrement availableCopies by 1.",
  "ground_truth": "The system returns 201 Created, creates a borrowing record, sets borrowDate and dueDate, leaves returnDate null, and decrements availableCopies by 1.",
  "contexts": [
    "FR-AUT-BORROW-002 Borrow Available Book acceptance criteria from docs/AUT_SRS_IEEE830_v1.md"
  ],
  "source": "docs/AUT_SRS_IEEE830_v1.md"
}
```

D 后续会用该结构计算 answer relevancy、faithfulness、context precision、context recall 等指标。

## 6. E 测试生成器输出接口预留

E 的 EP / BVA / DT 生成器应输出统一 test case schema。

```json
{
  "test_id": "TC-AUT-008-001",
  "requirement_id": "REQ-AUT-008",
  "coverage_item_id": "COV-AUT-BORROW-001",
  "technique": "DT",
  "title": "Borrow existing available book",
  "preconditions": ["Book exists", "Member exists", "availableCopies > 0"],
  "input_data": {
    "book.id": 1,
    "member.id": 1
  },
  "test_steps": [
    "POST /api/borrow with book.id and member.id"
  ],
  "expected_result": "201 Created; borrowing record created; availableCopies decreases by 1",
  "risk_level": "High",
  "standard_ref": "ISO/IEC/IEEE 29119-4 decision table testing"
}
```

D 的集成测试会重点检查：

- 是否保留 `requirement_id`；
- 是否保留 `coverage_item_id`；
- `technique` 是否匹配 requirement 中的推荐技术；
- 是否存在 `expected_result`；
- 是否存在 `standard_ref`；
- high priority requirement 是否至少生成一个测试用例。

## 7. C 前端展示接口预留

C 可以先使用 mock data 展示测试结果。字段应尽量与后端和 E 的输出一致。

```json
{
  "summary": {
    "total_requirements": 15,
    "generated_tests": 25,
    "high_risk_count": 8,
    "ci_status": "passing"
  },
  "test_cases": [
    {
      "test_id": "TC-AUT-008-001",
      "requirement_id": "REQ-AUT-008",
      "coverage_item_id": "COV-AUT-BORROW-001",
      "technique": "DT",
      "risk_level": "High",
      "status": "pass"
    }
  ],
  "ragas": {
    "enabled": false,
    "answer_relevancy": null,
    "faithfulness": null
  }
}
```

前端不应硬编码真实 live AUT 地址。AUT 地址应作为配置项或仅出现在 D 的测试说明中。

## 8. D 验收规则

D 后续会按以下规则做集成验收：

1. CI-safe tests 必须能在 GitHub Actions 中无外部服务运行。
2. live AUT tests 只在本地启动 AUT 后运行。
3. RAGAS tests 只有在 B 提供可复现 RAG 输出后才加入强制门禁。
4. 所有生成测试用例必须能追溯到 `requirement_id`。
5. FR3 生成结果必须能追溯到 `coverage_item_id`。
6. Interactive Review 修改必须能追溯到 `revision_id`。
7. 报告中的测试结果必须能追溯到 pytest 输出、CI 截图或 RAGAS 评分表。
