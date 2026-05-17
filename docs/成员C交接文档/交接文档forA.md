# C → A 交接文档

**写给**：A（Backend Lead）  
**来自**：C（Frontend & UX）  
**更新日期**：2026-05-15  
**依据**：`docs/integration_interfaces.md` · `docs/作业要求updated.md`

---

## 1. 你需要知道的事

1. C 已实现完整前端 + **参考后端** `backend/main.py`，默认 `http://localhost:8000`。
2. 你应在该契约上实现**正式 FastAPI**；字段不变则前端**无需改 UI**，标签自动变 **Live**。
3. CORS 必须允许：`http://localhost:5173`。
4. `/parse` 路由可由你暴露，但 **解析逻辑由 B 提供**；你负责转发与错误处理。

---

## 2. 你负责的接口

| 接口 | 方法 | Step | C 前端触发时机 | 参考后端 |
|------|------|------|----------------|----------|
| `/ingest` | POST | 1 | 解析 / 加载样本 | ✅ |
| `/parse` | POST | 1 | ingest 后对每条需求 | ✅（占位，待 B） |
| `/fsm` | POST | 3 | 进入 Step3 | ✅ |
| `/export` | POST | 4 | 导出 Approved | ✅ |
| `/export/{fmt}` | GET | 4 | 可选快速演示 | ✅ |
| `/dashboard` | GET | 全局 | 顶栏统计 | ✅ |
| `/health` | GET | — | 可选探活 | ✅ |

**不由你主责但需知悉**：`/risk`、`/coverage`、`/oracle`（B）；`/generate`、`/optimize`（E）。

---

## 3. `POST /ingest`

### 请求

```json
{
  "source_type": "text",
  "content": "<粘贴或文件内容；空字符串 = 加载 tests/data/aut_15_requirements.json 全部 15 条>"
}
```

### 响应

```json
{
  "requirements": [
    {
      "requirement_id": "REQ-AUT-008",
      "raw_requirement": "The system shall create a borrowing record...",
      "source": "aut_15_requirements"
    }
  ],
  "errors": []
}
```

- `errors` 非空时前端展示 Alert，不阻断流程。
- 单条粘贴时可用 `REQ-AUT-PASTE-001` 等临时 ID。

---

## 4. `POST /parse`

前端对 ingest 返回的**每条**需求串行调用（见 `frontend/src/services/api.ts`）。

### 请求

```json
{
  "requirement_id": "REQ-AUT-008",
  "raw_requirement": "..."
}
```

### 响应（含 B 的 Prompt 透明度字段）

```json
{
  "requirement_id": "REQ-AUT-008",
  "input_fields": ["book.id", "member.id"],
  "data_ranges": ["availableCopies: integer > 0"],
  "conditions": ["Book exists", "Member exists", "availableCopies > 0"],
  "expected_action": "Return 201, create a borrowing record...",
  "confidence": 0.88,
  "missing_fields": [],
  "source_context_ids": ["AUT_SRS:FR-AUT-BORROW-001"],
  "prompt_template_id": "PROMPT-FR1-V1",
  "retrieved_context_ids": ["AUT-SRS-001#FR-AUT-BORROW-001"],
  "model_name": "gpt-or-compatible-model",
  "output_schema_version": "parse-v1"
}
```

缺少 `input_fields` 等核心字段会导致 Step1 表格空白；Prompt 字段缺失时仅隐藏透明度面板。

---

## 5. `POST /fsm`

### 请求

```json
{ "requirement_ids": ["REQ-AUT-008", "REQ-AUT-012"] }
```

### 响应

```json
{
  "states": ["Available", "Borrowed", "Returned", "Rejected"],
  "transitions": [
    { "from": "Available", "to": "Borrowed", "event": "POST /api/borrow", "condition": "..." }
  ],
  "coverage": {
    "all_states": ["Available", "Borrowed", "Returned", "Rejected"],
    "all_transitions": ["Available->Borrowed", "Borrowed->Returned"]
  },
  "mermaid": "stateDiagram-v2\n    [*] --> Available\n    Available --> Borrowed: borrow\n    ..."
}
```

- `mermaid` 必须为 **stateDiagram-v2** 语法，前端用 `mermaid` 库渲染。
- `coverage.all_states` / `all_transitions` 用于路径覆盖标注列表。

---

## 6. `GET /dashboard`

顶栏 PipelineSummary 使用。

### 响应

```json
{
  "summary": {
    "total_requirements": 15,
    "generated_tests": 25,
    "high_risk_count": 8,
    "ci_status": "passing"
  },
  "ragas": {
    "enabled": false,
    "answer_relevancy": null,
    "faithfulness": null
  }
}
```

有 Step1/3 数据时前端会优先用本地 store 统计；无数据时用此接口。

---

## 7. `POST /export`（Step4 主路径）

### 请求

```json
{
  "format": "json",
  "test_cases": [ { "test_id": "TC-AUT-008-001", "status": "Approved", "..." } ],
  "risk_scores": [
    { "requirement_id": "REQ-AUT-008", "impact": 5, "likelihood": 5, "score": 25, "level": "High" }
  ],
  "coverage_items": [
    {
      "coverage_item_id": "COV-AUT-BORROW-008",
      "requirement_id": "REQ-AUT-008",
      "description": "...",
      "techniques": ["DT", "BVA"]
    }
  ],
  "revisions": [
    {
      "revision_id": "REV-0001",
      "session_id": "DS-AUT-001",
      "target_type": "requirement",
      "target_id": "REQ-AUT-008",
      "before": { "expected_action": "old" },
      "after": { "expected_action": "new" },
      "timestamp": "2026-05-15T10:00:00.000Z"
    }
  ]
}
```

说明：

- `test_cases`：**仅 Approved**（前端已过滤）。
- `revisions`：前端 `mapRevisionsForExport()` 已转为 D 契约；`session_id` 固定 `DS-AUT-001`。
- `risk_scores` / `coverage_items`：满足 FR6.0「Risk Scores + Test Cases」导出要求。

### 响应

- `format=json`：`Content-Type: application/json`，body 含上述四类数据 + `exported_at`。
- `format=csv`：扁平化 `test_cases` 行（参考实现中 xlsx 亦输出 csv）。

### `GET /export/{fmt}`

保留全量快速下载；**正式演示请以 POST 为准**（含 Approved 过滤与 revisions）。

---

## 8. 前端人工修订（不需你持久化）

以下仅存在 Zustand + 导出 body，**不要求** ingest/parse 回写：

- Step1：`expected_action`、`conditions`、`input_fields`、designer_confirmed
- Step2：risk `level`、coverage 字段、新增覆盖项
- Step3：用例字段、status、FSM 路径覆盖状态

若 Day10 需要服务端持久化 Design Session，可新增 `POST /session`、`POST /revisions`；当前前端不调用。

---

## 9. 验收清单

| 检查项 | 预期 |
|--------|------|
| `./start.sh` 后访问 5173 | Step1 显示 **Live** |
| 加载 15 条样本 | ingest 返回 15 条 |
| Step3 FSM 卡片 | Mermaid 图渲染 |
| Step4 导出 JSON | 含 test_cases、risk_scores、coverage_items、revisions |
| 关后端 | 各步显示 **Mock · 待接入** |

---

## 10. 参考文件

| 文件 | 说明 |
|------|------|
| `backend/main.py` | 你可 fork 后替换 |
| `backend/data_loader.py` | 读取 15 条需求 |
| `frontend/src/services/api.ts` | 请求/响应类型与 fallback |
| `tests/data/aut_15_requirements.json` | 样本 ID 来源 |
| `docs/integration_interfaces.md` | D 的权威契约 |

---

## 11. 联系与变更

- 接口字段变更：请 PR 同步更新 `integration_interfaces.md` 并 @C。
- 新增强制字段：告知 C 改 `types/index.ts` 与对应 Step 组件。
