# C → A 对接文档（更新版）

**写给**：A（AI / Backend Lead）  
**来自**：C（Frontend & UX）  
**更新日期**：对齐 `作业要求updated.md` + 交互式审查能力

---

## 1. 当前状态

C 已提供 **参考后端实现** `backend/main.py`，前端默认连接 `http://localhost:8000`。  
你可在该基础上替换为正式 FastAPI 实现；前端**接口契约不变**时无需改 UI。

启动参考后端：

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

前端：

```bash
cd frontend && npm run dev
```

---

## 2. 你负责的接口清单

| 接口 | 方法 | Step | 状态（参考后端） |
|------|------|------|------------------|
| `/ingest` | POST | 1 | ✅ 已实现 |
| `/parse` | POST | 1 | ✅ 已实现（B 逻辑可替换） |
| `/fsm` | POST | 3 | ✅ 已实现 |
| `/export` | POST | 4 | ✅ 已实现（含 revisions） |
| `/export/{fmt}` | GET | 4 | ✅ 已实现（全量，演示用） |

**CORS**：需允许 `http://localhost:5173`。

---

## 3. `POST /ingest`

**触发**：用户上传文件或粘贴文本后点击「执行解析」。

### 请求

```json
{
  "source_type": "text",
  "content": "<文件内容或粘贴文本；空字符串则加载全部 15 条样本需求>"
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

`errors` 非空时前端展示黄色 Alert，不中断流程。

---

## 4. `POST /parse`

**触发**：前端对 `/ingest` 返回的每条需求逐一调用（见 `frontend/src/services/api.ts`）。

### 请求

```json
{
  "requirement_id": "REQ-AUT-008",
  "raw_requirement": "..."
}
```

### 响应

```json
{
  "requirement_id": "REQ-AUT-008",
  "input_fields": ["book.id", "member.id"],
  "data_ranges": ["availableCopies: integer > 0"],
  "conditions": ["Book exists", "Member exists"],
  "expected_action": "Return 201, create borrowing record",
  "confidence": 0.85,
  "missing_fields": []
}
```

**注意**：Day 5 由 B 提供 LLM parse 逻辑，你负责 REST 封装；字段必须齐全，否则 Step 1 表格无法展示。

### 前端人工修订（仅前端 store，可不回写）

用户可在 Step 1 **行内编辑** `expected_action`、`conditions`，并点击「确认」。修订记录写入 `revisions[]`，导出时一并提交。

---

## 5. `POST /fsm`

**触发**：进入 Step 3 时自动调用。

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
  "mermaid": "stateDiagram-v2\n    [*] --> Available\n    ..."
}
```

---

## 6. `POST /export`（推荐，Step 4 主路径）

**触发**：用户点击「导出 Approved CSV/JSON」。

前端只提交 **status === Approved** 的用例 + 全部 `revisions`。

### 请求

```json
{
  "format": "json",
  "test_cases": [ { "test_id": "TC-AUT-008-001", "status": "Approved", ... } ],
  "revisions": [
    {
      "id": "REV-1",
      "step": 0,
      "entity_type": "requirement",
      "entity_id": "REQ-AUT-008",
      "field": "expected_action",
      "old_value": "...",
      "new_value": "...",
      "timestamp": "2026-05-11T..."
    }
  ]
}
```

### 响应

- `format=json`：返回 JSON 文件流
- `format=csv` / `xlsx`：返回 CSV（参考实现中 xlsx 亦为 csv）

导出字段需包含：`test_id`, `requirement_id`, `technique`, `preconditions`, `test_steps`, `expected_result`, `risk_level`, `standard_ref`。

### `GET /export/{fmt}`

保留用于快速演示；**正式交付请实现 POST /export**，以支持 Approved 过滤与 revision 元数据。

---

## 7. 验收方式

| 现象 | 含义 |
|------|------|
| Step 卡片标题旁 **绿色 Live** | 接口可用 |
| **橙色 Mock · 待接入** | 后端未启动或路径/字段不匹配 |

---

## 8. 参考文件

- 参考后端：`backend/main.py`
- 前端 API 层：`frontend/src/services/api.ts`
- 样本数据：`tests/data/aut_15_requirements.json`
