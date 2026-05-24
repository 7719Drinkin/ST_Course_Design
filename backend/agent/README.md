# 黑盒测试设计 Agent

`backend/agent` 是一个面向后端内部调用的黑盒测试设计工具模块。它接收需求文本，调用大模型完成需求拆解、测试要素分析、覆盖目标识别、黑盒技术分配、测试设计规格生成和测试用例草稿生成。

对外推荐只使用一个入口：

```python
from agent import generate_blackbox_tests

result = await generate_blackbox_tests(
    requirement_text="The system shall ...",
    rag_context=None,
)
```

调用方不需要了解内部的 `AgentPipeline`、`PromptBuilder`、`LLMClient` 或具体 Agent 角色。

## 模块定位

这个模块负责把一段需求文本转换成结构化黑盒测试设计结果。它是 `backend/app` 的平行模块，不依赖 FastAPI，不提供接口路由，也不负责数据库保存。

当前支持的黑盒测试技术：

- `EP`：等价类划分
- `BVA`：边界值分析
- `DT`：决策表测试

当前不实现：

- 文件上传
- FastAPI route
- 数据库持久化
- 前端交互
- 导出功能
- FSM
- Oracle
- Optimize

## 输入

### `requirement_text: str`

外部传入的需求字符串。通常由 app/service 层从前端请求、文件解析结果或其他业务流程中整理得到。

要求：

- 必须是非空字符串。
- 应尽量包含完整业务规则、输入字段、边界条件和期望行为。

### `rag_context: str | None`

可选的 RAG 检索上下文。可以包含：

- ISO/IEC/IEEE 29119-4 相关片段
- ISTQB 测试技术说明
- 项目领域背景
- AUT 相关知识

如果调用方传入 `rag_context`，Agent 会优先使用它。如果不传，当前 pipeline 会通过 `RAGClient` 调用同级 `rag` 包中的 `RagService`，并在生成测试设计规格前注入上下文。

## 输出

`generate_blackbox_tests()` 始终返回标准 JSON dict。

成功时：

```json
{
  "success": true,
  "data": {
    "requirements": [],
    "analyzed_requirements": [],
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

失败时：

```json
{
  "success": false,
  "error": "...",
  "failed_step": "...",
  "partial_data": {
    "requirements": [],
    "analyzed_requirements": [],
    "coverage_goals": [],
    "coverage_items": [],
    "test_design_specs": [],
    "test_cases": []
  },
  "prompts_used": []
}
```

## 内部链路

内部 pipeline 固定执行以下 6 个 Agent：

```text
RequirementParseAgent
→ RequirementAnalysisAgent
→ CoverageIdentificationAgent
→ TechniqueAssignmentAgent
→ TestDesignSpecAgent
→ TestCaseDraftAgent
```

各步骤职责：

| Agent | 职责 |
| --- | --- |
| `RequirementParseAgent` | 将原始需求拆成原子需求，只做初步结构化。 |
| `RequirementAnalysisAgent` | 分析输入字段、数据范围、条件、业务规则、期望动作。 |
| `CoverageIdentificationAgent` | 识别需要测试的业务覆盖目标。 |
| `TechniqueAssignmentAgent` | 为覆盖目标分配 `EP / BVA / DT`。 |
| `TestDesignSpecAgent` | 按单个 coverage item 展开测试设计规格。 |
| `TestCaseDraftAgent` | 将测试设计规格组装成测试用例草稿。 |

设计原则：

- `EP / BVA / DT` 只在 `TechniqueAssignmentAgent` 后出现。
- `TestDesignSpecAgent` 按 `coverage_item` 逐个生成，避免 prompt 过大。
- `TestCaseDraftAgent` 按 `test_design_spec` 逐个生成，避免重复塞入全量上下文。
- 每一步输出都会做基础字段校验。
- 最终会统一规范化 ID，并检查追溯链。

## ID 和追溯关系

Agent 会在最终阶段统一规范化 ID，降低 LLM 自行生成 ID 不一致的风险。

常见 ID 格式：

```text
REQ-AUT-001
CG-AUT-001-001
COV-AUT-001-BVA-001
SPEC-AUT-001-BVA-001
TC-AUT-001-001
```

最终会检查：

- `analyzed_requirements.requirement_id` 能追溯到 `requirements`
- `coverage_goals.requirement_id` 能追溯到 `analyzed_requirements`
- `coverage_items.coverage_goal_id` 能追溯到 `coverage_goals`
- `test_design_specs.coverage_item_id` 能追溯到 `coverage_items`
- `test_cases.coverage_item_id` 能追溯到 `coverage_items`
- `test_cases.spec_id` 能追溯到 `test_design_specs`

如果断链，会返回标准错误结果，不会假装成功。

## 质量门禁

返回成功结果前会执行最终质量门禁：

- 至少有一条 `coverage_item`
- 至少有一条 `test_design_spec`
- 至少有一条 `test_case`
- 每条测试用例必须包含 `requirement_id`、`coverage_item_id`、`spec_id`、`technique`、`expected_result`
- `expected_result` 不能为空
- `status` 必须是 `Draft`
- `technique` 只能是 `EP / BVA / DT`

质量门禁失败时，返回：

```json
{
  "success": false,
  "failed_step": "final_quality_gate",
  "error": "Final quality gate failed: ..."
}
```

## LLM 配置

当前只支持 DeepSeek API。

环境变量：

```text
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

说明：

- `DEEPSEEK_API_KEY` 必填。
- `DEEPSEEK_BASE_URL` 可选，默认 `https://api.deepseek.com`。
- `DEEPSEEK_MODEL` 可选，默认 `deepseek-chat`。
- DeepSeek API 兼容 OpenAI SDK，因此内部使用 `openai.AsyncOpenAI`。

## RAG 上下文

`rag_context` 有两种来源：

1. 调用方显式传入。
2. 调用方不传时，由 `AgentPipeline` 通过 `RAGClient` 自动检索。

RAG 检索只在进入 `TestDesignSpecAgent` 前发生，用于辅助生成 `standard_ref` 和测试设计依据。

当前目录关系是：

```text
backend/
├─ agent/
└─ rag/
```

`RAGClient` 会直接从同级 `rag` 包导入 `RagService`：

```python
from rag import RagService
```

为兼容从项目根目录或 `backend` 目录启动的两种方式，`RAGClient` 会在导入前准备最小 Python 路径，确保优先使用 `backend/rag`，而不是其他同名目录。

边界：

- Agent 不实现向量库。
- Agent 不管理知识库文件。
- RAG 适配集中在 `tools/rag_client.py`。
- RAG 具体检索逻辑仍属于 `backend/rag`。
- 不在各个 Agent 中散乱 import RAG。

## 运行示例

在 `backend` 目录下运行：

```powershell
python -m agent.examples.run_blackbox_agent
```

示例会读取 `.env`，构造一段 borrowing 需求，调用 `generate_blackbox_tests()`，并打印格式化 JSON。

## 契约检查脚本

在 `backend` 目录下运行：

```powershell
python -m agent.examples.test_blackbox_agent_contract
```

该脚本不依赖 pytest，只做最小契约检查：

- 返回值必须是 dict
- 必须包含 `success`
- 成功时必须包含 `data.test_cases`
- 每条 test case 至少有 `requirement_id`、`coverage_item_id`、`expected_result`

## 目录结构

```text
backend/agent/
├─ __init__.py
├─ runner.py
├─ core/
├─ pipeline/
├─ roles/
├─ prompts/
├─ tools/
└─ examples/
```

关键文件：

- `runner.py`：对外门面函数 `generate_blackbox_tests`
- `pipeline/agent_pipeline.py`：内部 6 步 Agent 编排
- `tools/llm_client.py`：DeepSeek 调用
- `tools/rag_client.py`：RAG 薄适配
- `tools/output_validator.py`：各阶段输出校验
- `tools/id_normalizer.py`：ID 规范化
- `tools/traceability_checker.py`：追溯链检查
- `tools/final_quality_gate.py`：最终质量门禁
- `tools/result_formatter.py`：稳定输出格式化

## 开发边界

这个模块不应该直接处理：

- HTTP 请求和响应
- FastAPI router
- 数据库写入
- 文件上传和解析
- Excel/Word/PDF 导出
- 前端状态管理

这些应由其他 backend 层或 frontend 层处理。`backend/agent` 只负责黑盒测试设计智能体流程本身。
