# Runner 流式输出与后端接口接收对应文档

本文档只说明一件事：后端调用 `generate_blackbox_tests_stream(...)` 后，`docs/后端接口对接文档.md` 里的每个后端接口应当接收哪个流式阶段输出，以及从该阶段 `output` 中取哪些字段。

## 1. 后端怎么调用 runner

后端接收到前端输入后，会把输入内容整理成字符串传给 agent 层。agent 拿到这个字符串后，直接调用 runner：

```python
generate_blackbox_tests_stream(requirement_text, rag_context)
```

这里的 `requirement_text` 就是前端传来的需求字符串。后端不需要再调用 `/parse`、`/risk`、`/coverage` 等分段函数。

最小调用方式：

```python
from fastapi.responses import StreamingResponse

from backend.agent import generate_blackbox_tests_stream


async def run_agent_pipeline(requirement_text: str, rag_context: str | None = None):
    return StreamingResponse(
        generate_blackbox_tests_stream(
            requirement_text=requirement_text,
            rag_context=rag_context,
        ),
        media_type="text/event-stream",
    )
```

## 2. Runner 流式事件格式

`generate_blackbox_tests_stream(requirement_text, rag_context=None)` 返回 SSE 字符串，主要事件有：

```text
event: stage
data: {
  "stage": "parse_requirements",
  "title": "需求解析",
  "status": "completed",
  "output": {}
}
```

失败时：

```text
event: stage_error
data: {
  "stage": "generate_tests",
  "status": "failed",
  "error": "..."
}
```

完成时：

```text
event: final
data: {
  "status": "completed",
  "final_output": {
    "test_cases": [],
    "fsm_test_cases": [],
    "all_test_cases": [],
    "oracle_results": []
  }
}
```

后端接口只需要关注 `event: stage` 中的：

| 字段 | 说明 |
|---|---|
| `stage` | 当前阶段名称 |
| `output` | 当前阶段产物 |

## 3. 后端接口接收对应关系

### 3.1 `/ingest`、`/ingest/file`

不接收 runner 流式输出。

这两个接口只负责暂存输入文本或文件。真正调用 runner 的接口应在读取到 `requirement_text` 后执行：

```python
generate_blackbox_tests_stream(requirement_text, rag_context)
```

### 3.2 `/parse`

接收 runner 阶段：

```text
stage = "parse_requirements"
```

从 `output` 中取：

| `/parse` 响应字段 | runner 输出字段 |
|---|---|
| `requirements` | `output.requirements` |
| `analyzed_requirements` | `output.analyzed_requirements` |
| `prompts_used` | `output.prompts_used` |

对应示例：

```json
{
  "stage": "parse_requirements",
  "output": {
    "requirements": [],
    "analyzed_requirements": [],
    "prompts_used": []
  }
}
```

### 3.3 `/risk`

接收 runner 阶段：

```text
stage = "analyze_risk"
```

从 `output` 中取：

| `/risk` 响应字段 | runner 输出字段 |
|---|---|
| `risk_analysis` | `output.risk_analysis` |
| `prompts_used` | `output.prompts_used` |

对应示例：

```json
{
  "stage": "analyze_risk",
  "output": {
    "risk_analysis": [],
    "prompts_used": []
  }
}
```

### 3.4 `/coverage`

接收 runner 阶段：

```text
stage = "identify_coverage"
```

从 `output` 中取：

| `/coverage` 响应字段 | runner 输出字段 |
|---|---|
| `coverage_goals` | `output.coverage_goals` |
| `prompts_used` | `output.prompts_used` |

对应示例：

```json
{
  "stage": "identify_coverage",
  "output": {
    "coverage_goals": [],
    "prompts_used": []
  }
}
```

### 3.5 `/strategy`

接收 runner 阶段：

```text
stage = "assign_strategy"
```

从 `output` 中取：

| `/strategy` 响应字段 | runner 输出字段 |
|---|---|
| `coverage_items` | `output.coverage_items` |
| `prompts_used` | `output.prompts_used` |

对应示例：

```json
{
  "stage": "assign_strategy",
  "output": {
    "coverage_items": [],
    "prompts_used": []
  }
}
```

### 3.6 `/generate`

接收 runner 阶段：

```text
stage = "generate_tests"
```

从 `output` 中取：

| `/generate` 响应字段 | runner 输出字段 |
|---|---|
| `test_design_specs` | `output.test_design_specs` |
| `test_cases` | `output.test_cases` |
| `prompts_used` | `output.prompts_used` |

对应示例：

```json
{
  "stage": "generate_tests",
  "output": {
    "test_design_specs": [],
    "test_cases": [],
    "prompts_used": []
  }
}
```

说明：这里的 `test_cases` 是 EP/BVA/DT 用例，不包含 FSM 用例。

### 3.7 `/fsm`

接收 runner 阶段：

```text
stage = "generate_fsm"
```

从 `output` 中取：

| `/fsm` 响应字段 | runner 输出字段 |
|---|---|
| `fsm` | `output.fsm` |
| `test_cases` | `output.test_cases` |
| `prompt_evidence` | 由 `output.prompts_used` 转换 |

对应示例：

```json
{
  "stage": "generate_fsm",
  "output": {
    "fsm": {},
    "test_cases": [],
    "prompts_used": []
  }
}
```

说明：`/fsm` 响应里的 `session_id` 不来自 runner，由后端从请求或会话中补上。

### 3.8 `/oracle`

接收 runner 阶段：

```text
stage = "generate_oracle"
```

从 `output` 中取：

| `/oracle` 响应字段 | runner 输出字段 |
|---|---|
| `oracle_results` | `output.oracle_results` |
| `prompt_evidence` | 由 `output.prompts_used` 转换 |

对应示例：

```json
{
  "stage": "generate_oracle",
  "output": {
    "oracle_results": [],
    "prompts_used": []
  }
}
```

说明：runner 会先合并 `/generate` 的 EP/BVA/DT 用例和 `/fsm` 的 FSM 用例，再统一送入 Oracle 阶段。

### 3.9 `/revisions`

不接收 runner 流式输出。

该接口只保存人工修订记录。

### 3.10 `/regenerate`

当前不直接接收 `generate_blackbox_tests_stream(...)` 的输出。

该接口是基于人工修订做差量再生成；如果后续也要流式化，应单独新增 revision runner，而不是复用完整需求输入 runner。

### 3.11 `/analysis`

不直接接收某一个 runner stage。

如果需要在一键生成后做分析，可以在收到以下阶段后综合生成：

| 分析所需数据 | runner 来源 |
|---|---|
| 需求 | `parse_requirements.output.requirements` |
| 覆盖项 | `assign_strategy.output.coverage_items` |
| EP/BVA/DT 用例 | `generate_tests.output.test_cases` |
| FSM 用例 | `generate_fsm.output.test_cases` |
| 最终总用例 | `final.final_output.all_test_cases` |

### 3.12 `/optimize`

不直接接收某一个 runner stage。

如果一键生成后立即优化，主要使用：

| 优化所需数据 | runner 来源 |
|---|---|
| `test_cases` | `final.final_output.all_test_cases` |
| `coverage_items` | `assign_strategy.output.coverage_items`，以及后端从 FSM 用例补出的 FSM 覆盖项 |
| `risk_results` | `analyze_risk.output.risk_analysis` 转换得到 |

### 3.13 `/export`

不直接接收某一个 runner stage。

导出接口应聚合前面已经接收到并保存的阶段产物：

| 导出字段 | runner 来源 |
|---|---|
| `requirements` | `parse_requirements.output.requirements` |
| `risk_results` | `analyze_risk.output.risk_analysis` 转换得到 |
| `coverage_items` | `assign_strategy.output.coverage_items` |
| `test_cases` | `final.final_output.all_test_cases` |
| `oracle_results` | `final.final_output.oracle_results` 或 `generate_oracle.output.oracle_results` |
| `prompt_evidence` | 各阶段 `output.prompts_used` 转换得到 |

## 4. 最终输出如何接收

收到：

```text
event = "final"
```

从 `final_output` 中取：

| 字段 | 说明 |
|---|---|
| `test_cases` | EP/BVA/DT 用例 |
| `fsm_test_cases` | FSM 用例 |
| `all_test_cases` | 全部测试用例，建议作为最终测试用例总表 |
| `oracle_results` | Oracle 审查结果 |

最终测试用例页面建议使用：

```text
final_output.all_test_cases
```

Oracle 结果页面建议使用：

```text
final_output.oracle_results
```

## 5. Prompt 字段怎么接收

runner 每个阶段的 `output.prompts_used` 都可以转成后端接口中的 `prompts_used` 或 `prompt_evidence`。

如果接口字段是 `prompts_used`，直接接收：

```text
response.prompts_used = output.prompts_used
```

如果接口字段是 `prompt_evidence`，后端转换：

| `prompt_evidence` 字段 | 来源 |
|---|---|
| `evidence_id` | 后端生成 |
| `session_id` | 当前会话 |
| `prompt_name` | `PromptRecord.name` |
| `target_id` | `coverage_item_id`、`spec_id` 或当前业务对象 ID |
| `input.prompt` | `PromptRecord.prompt` |
| `output` | 当前阶段结果摘要 |
| `created_at` | 后端生成 |

## 6. RAG 字段怎么接收

当前 `generate_blackbox_tests_stream(...)` 不单独返回结构化 RAG 字段。

也就是说现在没有这些独立字段：

| 字段 | 当前是否返回 |
|---|---|
| `rag_context` | 否 |
| `retrieved_context_ids` | 否 |
| `source_context_ids` | 否 |
| `rag_chunks` | 否 |
| `score` / `source` | 否 |

RAG 内容如果参与了 prompt，只会间接出现在：

```text
output.prompts_used[].prompt
```

如果后端接口必须返回结构化 RAG 证据，需要后续扩展 runner 或 `PromptRecord`。
