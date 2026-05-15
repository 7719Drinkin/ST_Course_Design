# C → E 对接文档（更新版）

**写给**：E（Algorithm / Backend Engineer）  
**来自**：C（Frontend & UX）  
**更新日期**：对齐交互式审查 + Approved 导出过滤

---

## 1. 当前状态

参考后端 `backend/main.py` 已实现 `/generate` 与 `/optimize`。  
你替换为正式 EP/BVA/DT 生成器与 set-cover 优化后，保持契约即可。

---

## 2. 你负责的接口

| 接口 | 方法 | Step | 说明 |
|------|------|------|------|
| `/generate` | POST | 3 | 统一测试用例生成 |
| `/optimize` | POST | 4 | 套件最小化 |

---

## 3. `POST /generate`

**触发**：进入 Step 3 自动调用。

### 请求

```json
{
  "requirement_ids": ["REQ-AUT-008", "REQ-AUT-012"],
  "coverage_items": []
}
```

`coverage_items` 可选；若 B 的 `/coverage` 已就绪，前端后续可传入覆盖项以约束生成。

### 响应

```json
[
  {
    "test_id": "TC-AUT-008-001",
    "requirement_id": "REQ-AUT-008",
    "technique": "DT",
    "title": "Borrow existing available book",
    "preconditions": ["Book exists", "Member exists", "availableCopies > 0"],
    "input_data": { "book.id": 1, "member.id": 1 },
    "test_steps": ["POST /api/borrow with { book.id: 1, member.id: 1 }"],
    "expected_result": "201 Created; borrowing record created",
    "risk_level": "High",
    "standard_ref": "ISO/IEC/IEEE 29119-4 §6.4 decision table testing",
    "status": "Draft",
    "coverage_item_id": "CI-REQ-AUT-008"
  }
]
```

### 字段要求（D 集成测试会检查）

| 字段 | 必填 |
|------|------|
| `test_id` | ✅ |
| `requirement_id` | ✅ |
| `technique` | ✅ EP/BVA/DT/FSM |
| `expected_result` | ✅ |
| `standard_ref` | ✅ |
| `status` | 建议返回 `Draft` |

### 前端交互（作业强制）

| 交互 | 说明 |
|------|------|
| 编辑 `expected_result` | 行内 Input |
| 修改 `risk_level` | 下拉 |
| 状态按钮 | Draft / Approved / Rejected |
| 追溯 | 点击 `requirement_id` 高亮关联需求 |
| 筛选 | 按 status 过滤 |

**仅 `Approved` 用例参与 Step 4 优化与导出。**

---

## 4. `POST /optimize`

**触发**：Step 4 进入时 + 切换优化模式时；请求体为 **已 Approved 的 test_id 列表**。

### 请求

```json
{
  "mode": "risk_priority",
  "test_ids": ["TC-AUT-008-001", "TC-AUT-012-001"]
}
```

`mode`：`risk_priority` | `normal`

### 响应

```json
{
  "before_count": 25,
  "after_count": 12,
  "mode": "risk_priority",
  "reduction_rate": 52,
  "removed_test_ids": ["TC-AUT-003-001", "TC-AUT-004-001"]
}
```

| 字段 | 说明 |
|------|------|
| `before_count` | 优化前用例数（通常 = 传入 test_ids 数量） |
| `after_count` | 优化后保留数 |
| `reduction_rate` | 整数百分比 |
| `removed_test_ids` | **建议提供**，Step 4 列表展示 |

---

## 5. 与 A 导出接口的关系

Step 4 导出走 `POST /export`（A 实现），body 由前端组装：

- `test_cases`：仅 Approved
- `revisions`：全流程人工修订记录

你无需实现导出，但需保证 optimize 结果与 Approved 集合一致。

---

## 6. 性能目标（NFR）

作业建议用例生成 ≤ 2s。若超时，前端会 fallback mock；请在文档中说明实际耗时与优化建议。

---

## 7. 验收

- Step 3 用例表显示 EP/BVA/DT 多种 technique
- Step 4 切换模式后 before/after 数值变化
- 标签 **Live** 表示对接成功
