# C → A 对接文档

**写给**：A（AI / Backend Lead）  
**来自**：C（Frontend & UX）

---

## 概述

前端 UI 已全部就绪，4 个步骤的页面都已完成并通过 mock 数据流验证。你完成对应接口后，前端**无需任何改动**，会自动切换为真实数据并显示绿色 "Live" 标签。

以下是前端正在等待的你的全部接口，按优先级排列。

---

## 接口 1：`POST /ingest`（Step 1 页面，最高优先级）

**前端调用时机**：用户上传文件后点击"执行解析"。  
**当前状态**：mock 兜底，Step 1 显示橙色 Mock 标签。

### 请求体

```json
{
  "source_type": "text",
  "content": "<文件内容字符串>"
}
```

`source_type` 目前前端只发 `"text"`，后续可扩展 `"csv"` / `"json"`。

### 期望返回

```json
{
  "requirements": [
    {
      "requirement_id": "REQ-AUT-001",
      "raw_requirement": "The system shall return a JSON array...",
      "source": "aut_15_requirements"
    }
  ],
  "errors": ["REQ-AUT-009: missing expected_action field"]
}
```

**注意**：前端会把 `errors` 展示为黄色 Alert，不会报错中断流程。

---

## 接口 2：`POST /parse`（Step 1 页面，与 /ingest 配套）

**前端调用时机**：`/ingest` 成功后，对每条需求逐一调用。  
**当前状态**：mock 兜底。

### 请求体

```json
{
  "requirement_id": "REQ-AUT-008",
  "raw_requirement": "The system shall create a borrowing record..."
}
```

### 期望返回

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

**说明**：`parse` 接口的 LLM 实现由 B 负责（Day 5），你负责将 B 的能力封装为 REST 接口暴露出来。

**前端使用字段**：全部字段均展示在 Step 1 的解析结果表格中。

---

## 接口 3：`POST /fsm`（Step 3 页面）

**前端调用时机**：进入 Step 3 页面时自动触发。  
**当前状态**：mock 兜底，FSM 面板显示橙色 Mock 标签。

### 请求体

```json
{
  "requirement_ids": ["REQ-AUT-008", "REQ-AUT-012", "REQ-AUT-001"]
}
```

### 期望返回

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
  "mermaid": "stateDiagram-v2\n    [*] --> Available\n    Available --> Borrowed : POST /api/borrow [copies > 0]\n    ..."
}
```

**前端使用**：
- `mermaid` 字段直接渲染在 FSM 面板的 `<pre>` 区域
- `coverage.all_transitions` 渲染为右侧覆盖路径列表

---

## 接口 4：`GET /export/json` / `GET /export/csv` / `GET /export/xlsx`（Step 4 页面）

**前端调用时机**：用户点击 Step 4 页面顶部的导出按钮时，直接 `window.open(url)` 触发下载。  
**当前状态**：按钮已就绪，但后端接口不存在时会报 404。

### 请求

无请求体，GET 请求，直接返回文件流（Content-Disposition: attachment）。

### 导出字段要求（参考 `integration_interfaces.md §3.4`）

| 字段 | 必填 |
|------|------|
| `test_id` | ✅ |
| `requirement_id` | ✅ |
| `technique` | ✅ |
| `preconditions` | ✅ |
| `test_steps` | ✅ |
| `expected_result` | ✅ |
| `risk_level` | ✅ |
| `standard_ref` | ✅ |

---

## 配置说明

前端默认连接 `http://localhost:8000`，可通过 `frontend/.env.local` 修改：

```
VITE_API_BASE=http://localhost:8000
```

**CORS**：请在后端启用 CORS 允许 `http://localhost:5173`（Vite 默认端口）。

---

## 对接验证方法

你的接口完成后，前端在对应 Step 的卡片标题旁会由橙色 **"Mock · 待接入"** 变为绿色 **"Live"**，即代表对接成功。无需前端修改任何代码。
