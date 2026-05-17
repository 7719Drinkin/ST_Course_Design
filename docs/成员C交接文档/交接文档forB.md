# C → B 交接文档

**写给**：B（AI / RAG Lead）  
**来自**：C（Frontend & UX）  
**更新日期**：2026-05-15  
**依据**：`docs/integration_interfaces.md` §5 · `docs/作业要求updated.md` Mainly 段落

---

## 1. 你需要知道的事

1. **Parse / Risk / Coverage / Oracle** 的 REST 路由在参考后端 `backend/main.py` 中；正式环境可能由 **A 统一暴露**，你提供业务逻辑即可。
2. 前端只认 **JSON 契约**；实现替换后 Step 标签由橙变 **Live**。
3. 作业 **Mainly** 要求 designer 可改覆盖项与策略 — Step2 已支持行内编辑，你的 `/coverage` 输出是生成依据。
4. **Prompt 透明度** 字段已在 Step1 展示，请尽量在 parse 响应中返回。

---

## 2. 你负责的接口

| 接口 | 方法 | Step | 前端行为 |
|------|------|------|----------|
| `/parse` | POST | 1 | 经 A 暴露；每条需求调用一次 |
| `/risk` | POST | 2 | 进入 Step2 自动调用 |
| `/coverage` | POST | 2 | 与 `/risk` 并行 |
| `/oracle` | POST | 3 | `/generate` 完成后按 test_id 列表调用 |

---

## 3. `POST /parse`（逻辑归你，路由归 A）

### 必须字段（FR 1.1）

| 字段 | 类型 | UI |
|------|------|-----|
| `input_fields` | string[] | 可编辑列 |
| `data_ranges` | string[] | 表格展示 |
| `conditions` | string[] | 可编辑列 |
| `expected_action` | string | 可编辑列 |
| `confidence` | float 0–1 | 颜色 Tag |
| `missing_fields` | string[] | 黄色 Alert |

### Prompt 透明度（建议返回，§5.2）

| 字段 | UI |
|------|-----|
| `source_context_ids` | Step1 折叠面板 |
| `prompt_template_id` | 同上 |
| `retrieved_context_ids` | 同上 |
| `model_name` | 同上 |
| `output_schema_version` | 同上 |
| `prompt_inputs` | 可选；C 可后续加 Modal |

示例：

```json
{
  "requirement_id": "REQ-AUT-008",
  "input_fields": ["book.id", "member.id", "availableCopies"],
  "data_ranges": ["availableCopies: integer > 0"],
  "conditions": ["Book exists", "Member exists", "availableCopies > 0"],
  "expected_action": "Return 201 and create a borrowing record",
  "confidence": 0.85,
  "missing_fields": [],
  "source_context_ids": ["AUT_SRS:FR-AUT-BORROW-002"],
  "prompt_template_id": "PROMPT-FR1-V1",
  "prompt_inputs": {
    "raw_requirement": "The system shall create a borrowing record..."
  },
  "retrieved_context_ids": ["AUT-SRS-001#FR-AUT-BORROW-002"],
  "model_name": "gpt-or-compatible-model",
  "output_schema_version": "parse-v1"
}
```

### 前端人工修订

用户可改 parse 结果并「确认」；修订不进你的模型，但会进入 `revisions` 导出供 D 审计。

---

## 4. `POST /risk`

### 请求

```json
{ "requirement_ids": ["REQ-AUT-008", "REQ-AUT-001"] }
```

空数组 = 对当前已加载需求全集评估（参考后端行为）。

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

| 约束 | 说明 |
|------|------|
| `impact`, `likelihood` | 整数 1–5 |
| `score` | 建议 `impact × likelihood` |
| `level` | `High` / `Medium` / `Low` |

### 前端交互

- 5×5 热力图：按 `(likelihood 行, impact 列)` 计数；**点击单元格筛选**明细表。
- 明细表展示 **Score**、**I×L**、**Priority 下拉**（人工覆盖 `level` → revisions）。

Risk Analysis Report §3 热力图截图可直接来自 Step2。

---

## 5. `POST /coverage`

对应 Mainly：**Coverage Item Identification + Coverage Strategy & Method**。

### 请求

```json
{ "requirement_ids": ["REQ-AUT-008"] }
```

### 响应

```json
[
  {
    "coverage_item_id": "COV-AUT-BORROW-008",
    "requirement_id": "REQ-AUT-008",
    "description": "Cover: Borrow an available book",
    "techniques": ["DT", "BVA", "FSM"],
    "strategy_rationale": "Selected DT, BVA per requirement techniques and AUT SRS context."
  }
]
```

### ID 规范（D 集成测试）

- 使用 `COV-AUT-{AREA}-{序号}`，例如 `COV-AUT-BORROW-008`。
- **勿用**旧格式 `CI-REQ-AUT-008`。

### 前端交互（已上线）

| 能力 | 说明 |
|------|------|
| 编辑 description | 行内 Input |
| 编辑 techniques | 多选 EP/BVA/DT/FSM |
| 编辑 strategy_rationale | 行内 Input |
| 新增覆盖项 | 前端生成 `COV-AUT-DESIGN-xxx`，带 `designer_added` 标记 |

E 的 `/generate` 应能消费你输出的 `coverage_item_id` 与 `techniques`（见 E 交接文档）。

---

## 6. `POST /oracle`

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

### 前端交互（FR 5.0）

- 独立 **Oracle 表**：LLM / Rule 判定 + 置信度颜色。
- `needs_review: true` → 显示 **Designer 确认** 按钮（将把用例标为 Approved）。
- 低置信度 + 用户修改 `expected_result` + 批准 = 演示 **interactive validation**。

---

## 7. RAGAS 与 A/B（D 使用，供你对齐）

RAGAS 样本结构见 `integration_interfaces.md` §5.3；`requirement_id`、`contexts` 需与 AUT SRS 一致。

前端 **不直接调用** RAGAS；你只需保证 parse/oracle 字段可供 D 脚本消费。

---

## 8. 可选扩展

| 能力 | 建议 |
|------|------|
| `GET /prompt-summary?requirement_id=` | Step3 侧栏只读展示 Prompt Design |
| `POST /regenerate` | Day10 差量再生（`revision_id` + `affected_coverage_item_ids`） |
| 回写 parse | 若需把 designer 修订反馈给模型，与 A 协商新接口 |

---

## 9. 验收清单

| 检查项 | 预期 |
|--------|------|
| Step1 解析后 | 有 confidence、Prompt 面板有内容 |
| Step2 | 热力图有数据；Coverage ID 为 `COV-AUT-*` |
| Step3 Oracle 表 | 有 llm/rule 判定；needs_review 可点确认 |
| 关后端 | Mock fallback，橙标 |

---

## 10. 参考文件

| 文件 | 说明 |
|------|------|
| `docs/AUT_SRS_IEEE830_v1.md` | fr_id / 需求溯源 |
| `tests/data/fr1_parse_output_template.json` | D 的 parse 样例 |
| `frontend/src/components/Step1InputParse.tsx` | Prompt UI |
| `frontend/src/components/Step2RiskAnalysis.tsx` | 风险 + 覆盖项 UI |
| `frontend/src/components/Step3GenerateEvaluate.tsx` | Oracle UI |
