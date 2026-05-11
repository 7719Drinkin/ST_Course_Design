# C → E 对接文档

**写给**：E（Algorithm / Backend Engineer）  
**来自**：C（Frontend & UX）

---

## 概述

前端 UI 已全部就绪。你负责的两个核心模块（测试用例生成和套件优化）的页面壳和展示逻辑均已完成，正在通过 mock 数据运行。你的接口上线后，前端**无需任何改动**，会自动切换为真实数据。

以下是前端正在等待你的全部接口。

---

## 接口 1：`POST /generate`（Step 3 页面，优先级高）

**前端调用时机**：用户进入 Step 3（Generate & Evaluate）时自动触发。  
**当前状态**：mock 兜底，用例表格显示橙色 Mock 标签。

### 请求体

```json
{
  "requirement_ids": ["REQ-AUT-008", "REQ-AUT-012", "REQ-AUT-001"]
}
```

若 `requirement_ids` 为空数组，则对全部已解析需求生成用例。

### 期望返回（对齐 `integration_interfaces.md §5`）

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
    "expected_result": "201 Created; borrowing record created; availableCopies − 1",
    "risk_level": "High",
    "standard_ref": "ISO/IEC/IEEE 29119-4 §6.4 decision table testing"
  },
  {
    "test_id": "TC-AUT-008-002",
    "requirement_id": "REQ-AUT-008",
    "technique": "BVA",
    "title": "Borrow with availableCopies = 1 (lower boundary)",
    "preconditions": ["Book exists", "Member exists", "availableCopies == 1"],
    "input_data": { "book.id": 2, "member.id": 1, "availableCopies": 1 },
    "test_steps": ["POST /api/borrow with availableCopies at boundary value 1"],
    "expected_result": "201 Created; availableCopies becomes 0",
    "risk_level": "High",
    "standard_ref": "ISO/IEC/IEEE 29119-4 §6.2 boundary value analysis"
  }
]
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `test_id` | string | 用例 ID，格式 `TC-AUT-xxx-xxx` |
| `requirement_id` | string | 来源需求 ID |
| `technique` | `EP` / `BVA` / `DT` / `FSM` | 测试技术，**前端用这个字段打蓝色标签** |
| `title` | string | 用例标题 |
| `preconditions` | string[] | 前置条件列表 |
| `input_data` | object | 输入数据（键值对） |
| `test_steps` | string[] | 测试步骤 |
| `expected_result` | string | 期望结果 |
| `risk_level` | `High` / `Medium` / `Low` | **前端用这个字段打颜色标签（红/黄/绿）** |
| `standard_ref` | string | 测试标准引用 |

**前端用这批数据做什么**：

1. 在 Step 3 的综合用例表格中展示所有用例（EP/BVA/DT 黑盒 + FSM 白盒混合显示）
2. 表格按 `technique`、`risk_level` 支持筛选
3. 每行用例通过 `test_id` 与 B 的 Oracle 结果关联，合并展示 Confidence 和复核状态
4. `standard_ref` 展示在表格最右列（可直接使用 ISO/ISTQB 引用文本）

---

## 接口 2：`POST /optimize`（Step 4 页面）

**前端调用时机**：用户进入 Step 4（Optimize & Export）时自动触发；用户切换优化模式时也会重新触发。  
**当前状态**：mock 兜底，Step 4 显示橙色 Mock 标签。

### 请求体

```json
{
  "mode": "risk_priority"
}
```

`mode` 枚举：`"risk_priority"` 或 `"normal"`。前端提供了切换开关，用户可随时切换，每次切换都会重新调用本接口。

### 期望返回（C 定义的展示结构）

```json
{
  "before_count": 25,
  "after_count": 12,
  "mode": "risk_priority",
  "reduction_rate": 52
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `before_count` | int | 优化前用例总数 |
| `after_count` | int | 优化后用例总数 |
| `mode` | string | 实际使用的优化模式 |
| `reduction_rate` | int | 缩减百分比（整数，例如 52 表示压缩了 52%） |

**前端用这批数据做什么**：

1. `before_count` 和 `after_count` 展示在两个并排大卡片中
2. `reduction_rate` 渲染为绿色进度条（缩减率）
3. 切换模式时（风险优先 vs 标准），用新一轮返回值刷新以上三个展示区

**可选扩展**（如果你能提供）：前端预留了 `selected_test_ids` 字段位，若你的接口能返回优化后保留的具体用例 ID 列表，前端可以在用例表格中高亮这些行，目前还未实现但可以后续加上。

---

## 配置说明

前端默认连接 `http://localhost:8000`，可通过 `frontend/.env.local` 修改：

```
VITE_API_BASE=http://localhost:8000
```

**CORS**：请确保后端允许 `http://localhost:5173`。

---

## 对接验证方法

你的接口完成后，前端对应卡片标题旁的橙色 **"Mock · 待接入"** 会自动变为绿色 **"Live"**，即代表对接成功。不需要 C 修改任何代码。

---

## 附：前端现有 mock 数据参考

以下是前端当前 mock 数据的字段形态（来自 `frontend/src/services/api.ts`），可用于验证你的返回格式是否符合前端期望：

```typescript
// mock TestCase 示例
{
  test_id: 'TC-AUT-008-001',
  requirement_id: 'REQ-AUT-008',
  technique: 'DT',
  title: 'Borrow existing available book',
  preconditions: ['Book exists', 'Member exists', 'availableCopies > 0'],
  input_data: { 'book.id': 1, 'member.id': 1 },
  test_steps: ['POST /api/borrow with { book.id: 1, member.id: 1 }'],
  expected_result: '201 Created; borrowing record created; availableCopies − 1',
  risk_level: 'High',
  standard_ref: 'ISO/IEC/IEEE 29119-4 §6.4 decision table testing',
}

// mock OptimizeResult 示例
{
  before_count: 3,
  after_count: 2,
  mode: 'risk_priority',
  reduction_rate: 33
}
```
