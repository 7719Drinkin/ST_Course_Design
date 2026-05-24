# 黑盒测试设计 Agent

`backend/agent` 是一个后端内部 Python 工具模块，用于把需求文本自动转成黑盒测试设计结果。它不负责 HTTP 路由、数据库、文件上传、导出、前端交互，也不实现 FSM / Oracle / Optimize。

推荐对外只使用门面函数：

```python
from agent import generate_blackbox_tests, generate_blackbox_tests_stream
```

## 能做什么

当前模块会一次性执行完整 Agent 链路：

```text
RequirementParseAgent
-> RequirementAnalysisAgent
-> RiskAnalysisAgent
-> CoverageIdentificationAgent
-> TechniqueAssignmentAgent
-> TestDesignSpecAgent
-> TestCaseDraftAgent
```

最终生成：

- `requirements`：拆分后的原子需求
- `analyzed_requirements`：输入、条件、范围、业务规则、期望动作
- `risk_analysis`：影响度、发生可能性、风险等级、测试优先级
- `coverage_goals`：要覆盖的业务场景
- `coverage_items`：分配后的 EP / BVA / DT 覆盖项
- `test_design_specs`：测试设计规格
- `test_cases`：测试用例草稿

## 同步调用

适合后端一次性拿最终结果：

```python
from agent import generate_blackbox_tests

result = await generate_blackbox_tests(
    requirement_text="The system shall allow a member to borrow a book when ...",
    rag_context=None,
)
```

成功返回：

```json
{
  "success": true,
  "data": {
    "requirements": [],
    "analyzed_requirements": [],
    "risk_analysis": [],
    "coverage_goals": [],
    "coverage_items": [],
    "test_design_specs": [],
    "test_cases": []
  },
  "metadata": {
    "case_count": 0,
    "coverage_item_count": 0,
    "requirement_count": 0,
    "techniques": ["BVA", "DT", "EP"],
    "has_rag_context": true
  },
  "prompts_used": []
}
```

失败返回统一错误结构，不会把内部异常直接抛给外部：

```json
{
  "success": false,
  "error": "...",
  "failed_step": "...",
  "partial_data": {},
  "prompts_used": []
}
```

## 流式调用

适合前端按阶段实时展示结果。用户仍然只提交一次 `requirement_text`，后端会连续执行完整 pipeline，不需要用户手动点“下一步”。

```python
from agent import generate_blackbox_tests_stream

async for chunk in generate_blackbox_tests_stream(requirement_text, rag_context=None):
    # chunk 是 SSE 文本片段，可以直接用于 StreamingResponse
    print(chunk)
```

每个阶段完成后会返回一个 SSE 事件：

```text
event: stage
data: {"stage":"risk_analysis","title":"风险分析","status":"completed","output":{...}}

```

最后返回：

```text
event: final
data: {"status":"completed","final_output":{"test_cases":[...]}}

```

如果某个阶段失败：

```text
event: stage_error
data: {"stage":"risk_analysis","status":"failed","error":"..."}

```

在 FastAPI 中接入时，可以在 app 层自行包装：

```python
from fastapi.responses import StreamingResponse
from agent import generate_blackbox_tests_stream

return StreamingResponse(
    generate_blackbox_tests_stream(requirement_text, rag_context),
    media_type="text/event-stream",
)
```

注意：`backend/agent` 本身不创建 FastAPI route。

## 风险分析

`RiskAnalysisAgent` 会为每个需求输出：

- `requirement_id`
- `impact`：1 到 5
- `likelihood`：1 到 5
- `risk_score = impact * likelihood`
- `risk_level`：`High / Medium / Low`
- `test_priority`：`P1 / P2 / P3`
- `risk_reason`

规则：

- `risk_score >= 15` -> `High` -> `P1`
- `risk_score >= 8` -> `Medium` -> `P2`
- 其他 -> `Low` -> `P3`

后续阶段会使用风险结果：

- 高风险需求会更关注异常路径、边界场景、核心业务场景。
- 高风险覆盖项可以拆成多个单独的 EP / BVA / DT 覆盖项。
- 测试用例会带上 `priority` 字段。

## RAG 上下文

`rag_context` 可以由外部显式传入。如果未传入，pipeline 会在进入 `TestDesignSpecAgent` 前通过 `tools/rag_client.py` 调用同级 `backend/rag` 中的 `RagService`。

边界：

- Agent 只消费 RAG 上下文。
- Agent 不实现向量库。
- Agent 不管理知识库文件。
- RAG 适配集中在 `tools/rag_client.py`。

## LLM 配置

当前只支持 DeepSeek API，使用环境变量：

```text
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

`DEEPSEEK_API_KEY` 必填。内部使用 `openai.AsyncOpenAI` 调用 DeepSeek 兼容接口。

## 质量门禁

每个阶段都有基础字段校验。最终返回前还会检查：

- 至少有一条 `coverage_item`
- 至少有一条 `test_design_spec`
- 至少有一条 `test_case`
- 测试用例必须包含 `requirement_id / coverage_item_id / spec_id / technique / preconditions / expected_result / priority`
- `expected_result` 不能为空
- `status` 必须是 `Draft`
- `technique` 只能是 `EP / BVA / DT`
- `priority` 只能是 `P1 / P2 / P3`
- 测试用例必须能追溯到已有 coverage item 和 design spec

## ID 规范

pipeline 结束前会统一规范 ID，降低 LLM 生成 ID 不一致带来的断链风险：

```text
REQ-AUT-001
CG-AUT-001-001
COV-AUT-001-BVA-001
SPEC-AUT-001-BVA-001
TC-AUT-001-001
```

## 当前不负责

- FastAPI route
- 数据库保存
- 文件上传和解析
- 前端状态管理
- Word / Excel / PDF 导出
- FSM
- Oracle
- Optimize
