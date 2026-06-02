# 黑盒测试设计 Agent

`backend/agent` 是后端内部的黑盒测试设计生成模块。它不提供 HTTP route，不管理数据库，也不负责前端状态；对外稳定入口是：

```python
from backend.agent import generate_blackbox_tests, generate_blackbox_tests_stream
```

## 分层职责

### core

- `core/models.py` 是唯一输出结构来源。字段、类型、枚举、默认值、非空字符串、`risk_score` 映射、`Draft` 状态等单对象规则都在这里定义。
- `core/agent_context.py` 是运行时容器，只在 Agent 之间传递强类型对象，不定义 schema。
- `core/base_agent.py` 统一处理 Prompt 构造、LLM JSON 调用、Prompt 记录，以及 LLM 输出到强类型模型的转换入口。

维护原则：如果一个字段是否合法只和它自己有关，改 `models.py`；不要在 tools 或 runner 里重复写字段表。

### roles

`roles/*.py` 是单个业务生成单元：

```text
RequirementParseAgent
RequirementAnalysisAgent
RiskAnalysisAgent
CoverageIdentificationAgent
TechniqueAssignmentAgent
TestDesignSpecAgent
TestCaseDraftAgent
```

每个 role 只做三件事：准备 prompt 变量、调用 LLM、用 `tools/validation/output_validator.py` 转成模型后写入 `AgentContext`。不要在 role 中手写 required fields、枚举或风险分数校验。

### pipeline

- `pipeline/agent_pipeline.py` 只提供阶段执行能力：`parse_requirements`、`analyze_risk`、`identify_coverage`、`assign_strategy`、`generate_tests`。
- `pipeline/finalizer.py` 负责把各阶段结果组装成 `FullPipelineResult`，然后统一执行 ID 规范化、追溯检查和最终门禁。
- `pipeline/stages.py` 统一定义对外阶段名和阶段标题。
- `pipeline/errors.py` 定义 `StageExecutionError`，runner 用它保留真实失败阶段。

不要在 `agent_pipeline.py` 里拼完整 workflow、格式化 API 响应或生成 SSE。

### tools

`tools` 按职责拆成三个子目录：

- `tools/clients/`
  - `llm_client.py`：只负责 LLM 调用。
  - `rag_client.py`：只负责 RAG 检索。
- `tools/validation/`
  - `output_validator.py`：只负责 `dict/list -> models.py` 强类型对象。
  - `id_gate.py`: validates ID format and references without rewriting LLM output.
  - `traceability_checker.py`：检查重复 ID 和同一条 requirement 链是否串错。
  - `final_quality_gate.py`：检查最终交付物是否齐备、引用是否存在、用例优先级是否回到风险分析。
- `tools/formatting/`
  - `json_parser.py`：只负责从 LLM 文本中提取 JSON。
  - `result_formatter.py`：只负责对外成功/失败响应格式。

`traceability_checker` 和 `final_quality_gate` 的区别：前者看链路是否一致，后者看最终结果是否达到可交付门槛。

## 完整流程

`runner.py` 是完整 workflow 的唯一编排入口：

```text
input_validation
-> parse_requirements
-> analyze_risk
-> identify_coverage
-> assign_strategy
-> generate_tests
-> final_validation
-> final
```

普通模式返回 `format_success_result(...)`；流式模式每个阶段完成后发送一次 `stage completed`，`final_validation` 通过后才发送 `final`。

## ID 规范化

finalizer 中的收尾顺序固定为：

```text
require_pipeline_id_formats(result)
check_traceability(result)
run_final_quality_gate(result)
```

ID 规范化必须先改上游 ID，再同步下游引用。例如先改 `requirement_id`，再同步风险、覆盖、规格和用例中的 `requirement_id`；再改 `coverage_item_id`，同步 spec 和 test case。这个顺序不能随意调整，否则会丢失旧 ID 到新 ID 的映射。

## 新增一个 Agent 阶段时

1. 在 `core/models.py` 增加阶段输出模型和 Result 模型。
2. 在 `tools/validation/output_validator.py` 增加对应的薄封装。
3. 在 `prompts/templates/` 增加模板，并在 `prompt_registry.py` 注册。
4. 在 `roles/` 增加 role agent，调用 `_run_validated_json_prompt(...)`。
5. 在 `pipeline/stages.py` 增加对外阶段名和标题。
6. 在 `pipeline/agent_pipeline.py` 增加阶段函数，只构建 context、调用 role、返回 Result。
7. 在 `runner.py` 的 `_iter_pipeline_stages(...)` 中插入阶段顺序。
8. 如果最终结果需要包含该阶段产物，更新 `pipeline/finalizer.py`、`FullPipelineResult` 和相关测试。

## 当前边界

本模块不负责：

- FastAPI route
- 数据库存储
- 文件上传和解析
- 前端状态管理
- Word / Excel / PDF 导出
- FSM / Oracle / Optimize
