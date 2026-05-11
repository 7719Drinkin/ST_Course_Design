# C → B 对接文档

**写给**：B（AI / RAG Lead）  
**来自**：C（Frontend & UX）

---

## 概述

前端 UI 已全部就绪。你负责的两个核心功能模块（风险分析和 Oracle 评估）的页面壳和展示逻辑均已完成，正在通过 mock 数据运行。你的接口上线后，前端**无需任何改动**，会自动切换为真实数据。

以下是前端正在等待你的全部接口。

---

## 接口 1：`POST /risk`（Step 2 页面，优先级高）

**前端调用时机**：用户进入 Step 2（Risk Analysis）时自动触发。  
**当前状态**：mock 兜底，Step 2 热力图显示橙色 Mock 标签。

### 请求体

```json
{
  "requirement_ids": ["REQ-AUT-001", "REQ-AUT-008", "REQ-AUT-012"]
}
```

若 `requirement_ids` 为空数组，则对全部需求评估。

### 期望返回（C 定义的展示结构）

```json
[
  { "requirement_id": "REQ-AUT-008", "impact": 5, "likelihood": 5, "score": 25, "level": "High" },
  { "requirement_id": "REQ-AUT-012", "impact": 4, "likelihood": 3, "score": 12, "level": "Medium" },
  { "requirement_id": "REQ-AUT-001", "impact": 2, "likelihood": 3, "score": 6,  "level": "Medium" }
]
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `requirement_id` | string | 需求 ID，格式 `REQ-AUT-xxx` |
| `impact` | int 1-5 | 影响程度评分 |
| `likelihood` | int 1-5 | 发生可能性评分 |
| `score` | int 1-25 | `impact × likelihood` |
| `level` | `High` / `Medium` / `Low` | 风险等级 |

**前端用这批数据做什么**：

1. **5×5 热力图矩阵**：按 `(likelihood, impact)` 坐标统计各象限的需求数量，用颜色深浅表示密度（绿/黄/红）
2. **Risk Snapshot 面板**：按 `level` 统计高/中/低风险需求总数
3. **明细表格**：展示每条需求的 ID、score、level

---

## 接口 2：`POST /parse`（Step 1 页面，由 A 暴露为接口）

**说明**：你负责 FR1.1 的 LLM Prompt 解析逻辑（Day 5），A 负责将其封装为 `POST /parse` REST 接口暴露给前端。前端调用的是 A 的接口，但 parse 结果的字段质量由你保证。

**你需要确保 parse 输出包含以下字段**（前端会展示全部）：

```json
{
  "requirement_id": "REQ-AUT-008",
  "input_fields": ["book.id", "member.id", "availableCopies"],
  "data_ranges": ["availableCopies: integer > 0"],
  "conditions": ["Book exists", "Member exists", "availableCopies > 0"],
  "expected_action": "Return 201, create borrowing record, decrement availableCopies by 1",
  "confidence": 0.85,
  "missing_fields": []
}
```

`confidence` 字段前端会用颜色分档展示：≥0.85 绿，≥0.70 金，<0.70 红。`missing_fields` 非空时会在 UI 中展示告警。

---

## 接口 3：`POST /oracle`（Step 3 页面）

**前端调用时机**：用户进入 Step 3（Generate & Evaluate）时自动触发。  
**当前状态**：mock 兜底，Oracle 列显示橙色 Mock 标签。

### 请求体

```json
{
  "test_ids": ["TC-AUT-008-001", "TC-AUT-008-002", "TC-AUT-012-001"]
}
```

若 `test_ids` 为空，则对全部可见用例评估。

### 期望返回（C 定义的展示结构）

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

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `test_id` | string | 关联用例 ID，格式 `TC-AUT-xxx-xxx` |
| `llm_verdict` | `Pass` / `Fail` | LLM 语义判断结果 |
| `rule_verdict` | `Pass` / `Fail` | 规则断言结果 |
| `confidence` | float 0-1 | 综合置信度分数 |
| `needs_review` | bool | 是否需要人工复核 |

**前端用这批数据做什么**：

1. Oracle 结果通过 `test_id` 与用例表格关联后合并展示在同一行
2. `confidence` 用颜色分档标签展示（绿 ≥0.85 / 金 ≥0.70 / 红 <0.70）
3. `needs_review: true` 的行在最右列展示红色"待复核"操作按钮
4. `llm_verdict` 和 `rule_verdict` 字段预留了展示位

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
