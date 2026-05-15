# C → B 对接文档（更新版）

**写给**：B（AI / RAG Lead）  
**来自**：C（Frontend & UX）  
**更新日期**：对齐交互式审查 + 新增 `/coverage` 接口

---

## 1. 当前状态

参考后端 `backend/main.py` 已提供 `/risk`、`/oracle`、`/coverage` 的占位实现。  
你替换为真实 RAG/LLM 逻辑后，保持下列 JSON 契约即可，前端自动显示 **Live**。

---

## 2. 你负责的接口

| 接口 | 方法 | Step | 说明 |
|------|------|------|------|
| `/parse` | POST | 1 | 由 A 暴露；**字段质量由你保证** |
| `/risk` | POST | 2 | 风险矩阵数据 |
| `/coverage` | POST | 2 | **新增** 覆盖项与测试策略 |
| `/oracle` | POST | 3 | Oracle 评估 |

---

## 3. `POST /parse`（通过 A 暴露）

前端展示字段（你必须保证 parse 输出包含）：

| 字段 | 类型 | UI 用途 |
|------|------|---------|
| `input_fields` | string[] | 表格列 |
| `data_ranges` | string[] | 可扩展展示 |
| `conditions` | string[] | 可编辑列 |
| `expected_action` | string | 可编辑列 |
| `confidence` | float 0–1 | 颜色标签 |
| `missing_fields` | string[] | 告警 |

---

## 4. `POST /risk`

**触发**：进入 Step 2 自动调用。

### 请求

```json
{ "requirement_ids": ["REQ-AUT-008", "REQ-AUT-001"] }
```

空数组 = 评估全部已 ingest 需求。

### 响应

```json
[
  {
    "requirement_id": "REQ-AUT-008",
    "impact": 5,
    "likelihood": 5,
    "score": 25,
    "level": "High"
  }
]
```

| 字段 | 约束 |
|------|------|
| `impact`, `likelihood` | 整数 1–5 |
| `score` | 建议 `impact × likelihood` |
| `level` | `High` / `Medium` / `Low` |

### 前端交互

- 5×5 热力图按 `(likelihood, impact)` 统计数量
- 明细表 **Priority 下拉框**可人工覆盖 `level`（修订记入 `revisions`）

---

## 5. `POST /coverage`（新增）

**触发**：Step 2 进入时与 `/risk` 并行调用。

### 请求

```json
{ "requirement_ids": ["REQ-AUT-008"] }
```

### 响应

```json
[
  {
    "coverage_item_id": "CI-REQ-AUT-008",
    "requirement_id": "REQ-AUT-008",
    "description": "Cover: Borrow an available book",
    "techniques": ["DT", "BVA", "FSM"],
    "strategy_rationale": "Selected DT, BVA per requirement techniques field."
  }
]
```

对应作业 **Mainly** 流程中的 Coverage Item Identification + Coverage Strategy & Method。  
后续 E 的 `/generate` 可读取这些覆盖项作为输入。

---

## 6. `POST /oracle`

**触发**：Step 3 在 `/generate` 完成后，对返回的 `test_id` 列表调用。

### 请求

```json
{ "test_ids": ["TC-AUT-008-001", "TC-AUT-008-002"] }
```

### 响应

```json
[
  {
    "test_id": "TC-AUT-008-001",
    "llm_verdict": "Pass",
    "rule_verdict": "Pass",
    "confidence": 0.95,
    "needs_review": false
  },
  {
    "test_id": "TC-AUT-008-002",
    "llm_verdict": "Pass",
    "rule_verdict": "Fail",
    "confidence": 0.56,
    "needs_review": true
  }
]
```

### 前端交互

- `confidence` 颜色：≥0.85 绿，≥0.70 金，<0.70 红
- `needs_review: true` 时用户可在 Step 3 将用例标为 Approved/Rejected
- 低置信度用例修改 `expected_result` 后批准 = 演示 **interactive validation**

---

## 7. Prompt Design 展示（可选）

作业要求展示 Prompt Design。建议在 `/oracle` 或单独 `GET /prompt-summary` 返回：

```json
{
  "requirement_id": "REQ-AUT-008",
  "prompt_summary": "Few-shot parse with AUT SRS context...",
  "source_context_ids": ["AUT_SRS:FR-AUT-BORROW-002"]
}
```

前端可在 Step 3 增加只读 Modal；若你提供字段，C 可快速接入。

---

## 8. 验收

后端启动后 Step 2/3 标签由橙色变绿色 **Live**。  
Risk Report §3 热力图截图可直接来自 Step 2 UI。
