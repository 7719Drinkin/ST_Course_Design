# C → E 交接文档

**写给**：E（Algorithm / Backend Engineer）  
**来自**：C（Frontend & UX）  
**更新日期**：2026-05-15  
**依据**：`docs/integration_interfaces.md` · `tests/data/generated_test_cases_template.json`

---

## 1. 你需要知道的事

1. 参考后端 `backend/main.py` 已实现 `/generate`、`/optimize` 占位逻辑。
2. 前端 Step3 **仅展示并编辑** 你的输出；Step4 **仅对 Approved 用例** 调 optimize 与 export。
3. D 的集成测试会检查 `coverage_item_id`、`technique`、`standard_ref` 等字段。
4. Step2 人工编辑的 **coverage_items** 存在前端 store；后续版本可由 C 传入 `/generate` 的 `coverage_items` 数组（契约已预留）。

---

## 2. 你负责的接口

| 接口 | 方法 | Step | 前端触发 |
|------|------|------|----------|
| `/generate` | POST | 3 | 进入 Step3（requirements 变化时） |
| `/optimize` | POST | 4 | 进入 Step4 + 切换优化模式 |

---

## 3. `POST /generate`

### 请求

```json
{
  "requirement_ids": ["REQ-AUT-008", "REQ-AUT-012"],
  "coverage_items": []
}
```

| 字段 | 说明 |
|------|------|
| `requirement_ids` | Step1 已加载的需求 ID；空则参考后端用全量 15 条 |
| `coverage_items` | **建议读取** B 的覆盖项；当前前端传 `[]`，后续可改为 store 中的 `coverageItems` |

### 响应（单条用例）

```json
{
  "test_id": "TC-AUT-008-001",
  "requirement_id": "REQ-AUT-008",
  "coverage_item_id": "COV-AUT-BORROW-008",
  "technique": "DT",
  "title": "Borrow existing available book",
  "preconditions": ["Book exists", "Member exists", "availableCopies > 0"],
  "input_data": { "book.id": 1, "member.id": 1 },
  "test_steps": ["POST /api/borrow with valid book.id and member.id"],
  "expected_result": "201 Created; borrowing record created; availableCopies decremented",
  "risk_level": "High",
  "standard_ref": "ISO/IEC/IEEE 29119-4 §6.4 decision table testing",
  "status": "Draft"
}
```

### D 集成测试必填

| 字段 | 要求 |
|------|------|
| `test_id` | `TC-AUT-xxx` |
| `requirement_id` | 与样本 JSON 一致 |
| `coverage_item_id` | **`COV-AUT-*`**，与 B coverage 对齐 |
| `technique` | `EP` / `BVA` / `DT` / `FSM`，且与需求推荐技术匹配 |
| `expected_result` | 非空 |
| `standard_ref` | 非空，建议 ISO 29119-4 章节引用 |
| `status` | 建议默认 `Draft` |

### 黑盒技术覆盖（FR 3.0）

- 同一需求应能体现 **至少三种** 技术（EP/BVA/DT）中的多种；演示时 Step3 顶栏有 EP/BVA/DT/FSM 计数 Tag。
- High priority 需求（如 REQ-AUT-008）应至少生成 1 条用例。

---

## 4. 前端交互（作业 Mainly — 已实现）

| 交互 | 字段 | 写入 revisions |
|------|------|----------------|
| 行内编辑 | `title`, `test_steps`, `expected_result` | ✅ |
| 下拉 | `risk_level` | ✅ |
| 状态按钮 | `Draft` / `Approved` / `Rejected` | ✅ |
| 点击 Req ID | 追溯面板 + 行高亮 | — |
| 筛选 | technique、status | — |

**仅 `status === Approved` 的用例：**

- 进入 Step4 `POST /optimize` 的 `test_ids`
- 进入 `POST /export` 的 `test_cases`

---

## 5. `POST /optimize`

### 请求

```json
{
  "mode": "risk_priority",
  "test_ids": ["TC-AUT-008-001", "TC-AUT-012-001"]
}
```

- `mode`：`risk_priority` | `normal`（前端 Segmented 切换）
- `test_ids`：**仅 Approved**（前端已过滤）

### 响应

```json
{
  "before_count": 5,
  "after_count": 3,
  "mode": "risk_priority",
  "reduction_rate": 40,
  "removed_test_ids": ["TC-AUT-003-001", "TC-AUT-004-001"]
}
```

| 字段 | UI |
|------|-----|
| `before_count` / `after_count` | 对比卡片 |
| `reduction_rate` | Progress 条（整数百分比） |
| `removed_test_ids` | **建议提供**，列表展示 |

---

## 6. 与覆盖项、追溯的关系

```
B: POST /coverage  →  coverage_item_id + techniques + strategy
        ↓
E: POST /generate  →  test_cases[].coverage_item_id 必须可追溯
        ↓
C: TraceabilityPanel  →  需求 ID → 覆盖项 → 用例
```

若生成时忽略 B 的覆盖项，UI 追溯链会断裂，影响作业 **Coverage & Effectiveness** 评分。

---

## 7. 性能（NFR）

- 作业建议生成 ≤ **2s**。
- 超时后前端仍显示结果（若返回），但会 Alert 提示未达 NFR；请在文档注明实测耗时与优化方向。

---

## 8. 导出（A 实现，与你相关）

你不实现 `/export`，但需保证：

- Approved 集合与 optimize 的 `test_ids` 一致；
- 被 `removed_test_ids` 剔除的用例不应再出现在 Approved 导出中（若 optimize 在 export 之前执行，由流程保证）。

导出 JSON 结构（A）：

```json
{
  "test_cases": [ "..." ],
  "risk_scores": [ "..." ],
  "coverage_items": [ "..." ],
  "revisions": [ "..." ],
  "exported_at": "..."
}
```

---

## 9. 验收清单

| 检查项 | 预期 |
|--------|------|
| Step3 用例表 | 含 EP/BVA/DT 多种 technique |
| Coverage ID 列 | `COV-AUT-BORROW-008` 格式 |
| 批准 1 条后 Step4 | optimize 的 before_count ≥ 1 |
| 导出 JSON | 仅含 Approved 用例 |
| **Live** 标签 | 后端正常时绿色 |

---

## 10. 参考文件

| 文件 | 说明 |
|------|------|
| `algorithm/` | 你的正式实现目录 |
| `tests/data/generated_test_cases_template.json` | D 用例模板 |
| `tests/data/aut_15_requirements.json` | 15 条需求与 techniques |
| `backend/main.py` | `_build_test_cases()` 占位逻辑 |
| `frontend/src/components/Step3GenerateEvaluate.tsx` | 用例表 UI |
| `frontend/src/components/Step4OptimizeExport.tsx` | 优化与导出 UI |

---

## 11. 后续联调建议

1. 先保证单需求 `REQ-AUT-008` 生成 3+ 条不同 technique 用例。
2. 再对接全量 15 条，观察 Step3 加载时间与 2s NFR。
3. 与 B 对齐 `coverage_item_id` 生成规则后，通知 C 开启 `generate` 请求体中的 `coverage_items` 传递（一行改动在 `api.ts`）。
