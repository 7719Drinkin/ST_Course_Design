# FR3 / FR4 后端接入说明

## 1. 文档目的

这份文档只解决一件事：**基于当前仓库代码，后端应该如何把 FR3 和 FR4 真正接到 app 层接口上**。

这里的 FR 编号按当前代码注释约定理解：

- **FR3**：`/coverage` -> `/strategy` -> `/generate`
- **FR4**：`/fsm`

注意：这和 [软件需求文档](./软件需求文档.md) 里从 FR4 开始展开的编号方式不完全一致。写代码时请以当前仓库里的 `agent/runner.py`、`agent/pipeline/agent_pipeline.py` 为准。

## 2. 先说结论

当前仓库里，**FR3/FR4 的真正实现入口在 `backend/agent/`，不是 `backend/app/modules/` 里的旧 service**。

推荐接法只有两种：

1. **分步接口接法（推荐给现有前端）**
   - `/coverage` 直接调用 `AgentPipeline.identify_coverage(...)`
   - `/strategy` 直接调用 `AgentPipeline.assign_strategy(...)`
   - `/generate` 直接调用 `AgentPipeline.generate_tests(...)`
   - `/fsm` 直接调用 `AgentPipeline.generate_fsm(...)`
2. **一键流式接法（推荐给整链路运行页）**
   - 直接调用 `generate_blackbox_tests_stream(...)`
   - 从 stage 事件中拆出 FR3/FR4 阶段结果

还有一个必要前提：

- `AgentPipeline` 这些阶段入口都是 `async`
- 所以 `/coverage`、`/strategy`、`/generate` 对应的 service 方法如果改成直连 pipeline，**service 和 router 都要改成异步调用并补 `await`**

**不建议的接法：**

- 不要继续保留 `app/modules/coverage_strategy/service.py` 里返回空数组的 TODO 实现。
- 不要继续使用 `app/modules/test_design/service.py` 里已经清空的 `/generate` 和 `/fsm` 旧接入。
- 不要把 `app/modules/fsm/` 当成当前 FR4 正式入口。它的 router 现在没有挂到 `main.py`，而且响应契约也不是前端现在在用的那套。

## 3. 当前代码现状

### 3.1 app 层现状

`backend/main.py` 当前挂载的是这些 router：

- `app.modules.intake_parse.router`
- `app.modules.concept_risk.router`
- `app.modules.coverage_strategy.router`
- `app.modules.test_design.router`
- `app.modules.evidence_improve.router`
- `app.modules.optimize_export.router`

其中和 FR3/FR4 直接相关的实际状态如下：

| 位置 | 当前状态 | 结论 |
|---|---|---|
| `backend/app/modules/coverage_strategy/service.py` | `/coverage`、`/strategy` 还是 TODO，直接返回空数组 | 需要改成直连 `AgentPipeline` |
| `backend/app/modules/test_design/service.py` | `/generate` 返回空结果 | 需要改成直连 `AgentPipeline.generate_tests(...)` |
| `backend/app/modules/test_design/service.py` | `/fsm` 返回空 `fsm`，并写入 `fsm_enabled=false` 的提示证据 | 需要改成直连 `AgentPipeline.generate_fsm(...)` |
| `backend/app/modules/test_design/service.py` | `/oracle` 已经在调用 `AgentPipeline.generate_oracles(...)` | 这是 FR3/FR4 接入时最接近可复用的参考写法 |
| `backend/app/modules/fsm/` | 有独立 `/fsm` router/service/schema，但未注册到 `main.py` | 不要把它当成正式接入点 |

### 3.2 agent 层现状

FR3/FR4 已经有可复用的正式能力：

| 能力 | 入口 |
|---|---|
| FR3 覆盖目标识别 | `AgentPipeline.identify_coverage(...)` |
| FR3 技术分配 | `AgentPipeline.assign_strategy(...)` |
| FR3 用例生成 | `AgentPipeline.generate_tests(...)` |
| FR4 FSM 建模 | `AgentPipeline.generate_fsm(...)` |
| FR3/FR4 整链路编排 | `generate_blackbox_tests(...)` / `generate_blackbox_tests_stream(...)` |

另外，`backend/app/modules/evidence_improve/service.py` 已经在直接调用：

- `pipeline.identify_coverage(...)`
- `pipeline.assign_strategy(...)`
- `pipeline.generate_tests(...)`

这说明“app service 直接调 `AgentPipeline`”本身就是仓库里已经采用的模式，不是新架构。

## 4. 推荐接入方案

### 4.1 方案 A：分步接口接入

这是最适合当前前端页面拆分方式的方案。

### `/coverage`

请求体继续沿用 `CoverageRequest`：

```json
{
  "analyzed_requirements": [],
  "risk_analysis": []
}
```

service 层建议改成 `async def` 后再调用：

```python
result = await AgentPipeline().identify_coverage(
    request.analyzed_requirements,
    request.risk_analysis,
)
```

返回映射：

- `response.coverage_goals = result.coverage_goals`
- `response.prompts_used = 需要把 agent PromptRecord 转成 app PromptRecord`

是否持久化：

- 可不存 `coverage_goals`
- 如果后端想做“纯 session 串联，不依赖前端回传”，需要先扩展 `workflow_store`，因为当前 store 里没有 `coverage_goals`
- 当前 `CoverageRequest` 也没有 `session_id`，如果要做服务端持久化链路，建议一并补上

### `/strategy`

请求体继续沿用 `StrategyRequest`：

```json
{
  "coverage_goals": [],
  "analyzed_requirements": [],
  "risk_analysis": []
}
```

service 层建议改成 `async def` 后再调用：

```python
result = await AgentPipeline().assign_strategy(
    request.coverage_goals,
    request.analyzed_requirements,
    request.risk_analysis,
)
```

返回映射：

- `response.coverage_items = result.coverage_items`
- `response.prompts_used = 需要转换`

建议持久化：

- `workflow_store.save_many(session_id, "coverage_items", ..., "coverage_item_id")`

说明：

- 当前 `StrategyRequest` 本身没有 `session_id`
- 如果要做服务端持久化，最好补 `session_id`；否则只能保持“前端带着结果走下一步”的模式

### `/generate`

请求体继续沿用 `GenerateRequest`：

```json
{
  "coverage_items": [],
  "risk_analysis": [],
  "rag_context": null
}
```

service 层建议改成 `async def` 后再调用：

```python
result = await AgentPipeline().generate_tests(
    request.coverage_items,
    request.risk_analysis,
    request.rag_context,
)
```

返回映射：

- `response.test_design_specs = result.test_design_specs`
- `response.test_cases = result.test_cases`
- `response.prompts_used = 需要转换`

建议持久化：

- `workflow_store.save_many(session_id, "test_cases", ..., "test_id")`

说明：

- `generate_tests(...)` 在没有 `rag_context` 时会自己补做一次 RAG 检索，app 层不需要额外先调 `rag/`
- 当前 `workflow_store` 没有 `test_design_specs` 集合，如果只是给前端展示，可以不存；如果后端后续要复用，需要扩展 store
- 当前 `GenerateRequest` 也没有 `session_id`，如果这里要落 session store，建议补字段

### `/fsm`

请求体继续沿用 `FsmRequest`：

```json
{
  "session_id": "SESSION-CURRENT",
  "requirements": [],
  "parsed_requirements": [],
  "coverage_items": [],
  "state_candidates": []
}
```

service 层建议改成 `async def` 后再调用：

```python
result = await AgentPipeline().generate_fsm(
    requirements=request.requirements or [],
    parsed_requirements=request.parsed_requirements or [],
    coverage_items=request.coverage_items or [],
    state_candidates=request.state_candidates or [],
)
```

返回映射：

- `response.session_id = request.session_id`
- `response.fsm = result.fsm`
- `response.test_cases = result.test_cases`
- `response.prompt_evidence = 由 result.prompts_used 转换`

建议持久化：

- `workflow_store.save_object(session_id, "fsm", result.fsm)`
- `workflow_store.save_many(session_id, "test_cases", result.test_cases, "test_id")`
- `workflow_store.save_many(session_id, "prompt_evidence", prompt_evidence, "evidence_id")`

说明：

- FR4 用例后续也要进入 `/oracle`、`/optimize`、`/export`，所以**建议和 FR3 用例一样落到 `test_cases` 集合里**
- `FsmTransition` 要按别名输出成 `from`，不要把字段名变成 `from_state`

### 4.2 方案 B：统一走 runner

如果后端要做“一键生成 + 进度流式展示”，直接使用：

```python
from backend.agent import generate_blackbox_tests_stream
```

FR3 / FR4 对应的 stage 为：

| stage | 含义 |
|---|---|
| `identify_coverage` | FR3 覆盖目标识别 |
| `assign_strategy` | FR3 技术分配 |
| `generate_tests` | FR3 用例生成 |
| `generate_fsm` | FR4 FSM 建模 |

这一块的字段拆法可以直接参考 [runner流式后端接口对接文档](./runner流式后端接口对接文档.md)。

但是要注意一个差异：

- `runner._run_fr4_branch(...)` 当前只把 `requirements` 和 `parsed_requirements` 送进 `generate_fsm(...)`
- **没有**把 `coverage_items` 和 `state_candidates` 送进去

所以：

- 如果你要的是“完整 FR4 单接口能力”，优先走 `AgentPipeline.generate_fsm(...)`
- 如果你要的是“整条主流程一次性跑通”，再走 runner

## 5. 字段转换注意事项

### 5.1 PromptRecord 不能直接原样返回

agent 层的 `PromptRecord` 字段是：

- `name`
- `prompt`
- `coverage_item_id`
- `spec_id`

app 层 schema 里的 `PromptRecord` 字段是：

- `prompt_name`
- `target_id`
- `input`
- `output`
- `note`
- `created_at`

所以 FR3 的 `/coverage`、`/strategy`、`/generate` 如果要返回 `prompts_used`，需要做一次转换，不能把 agent model 直接塞回 app response。

建议最少转换成：

```python
PromptRecord(
    prompt_name=item.name,
    target_id=item.coverage_item_id or item.spec_id,
    input={"prompt": item.prompt},
    output={},
    note="Generated by AgentPipeline stage",
    created_at=timestamp,
)
```

FR4 的 `/fsm` 更适合转成 `PromptEvidence`，做法可以参考当前 `/oracle` 和 `evidence_improve/service.py` 里的证据构造方式。

### 5.2 `FsmTransition.from` 必须保留别名

agent 层 FSM 模型内部字段是：

- Python 字段名：`from_state`
- JSON 别名：`from`

因此对外返回或写入 store 时，建议统一使用：

```python
model_dump(mode="json", by_alias=True)
```

否则前端会收到 `from_state`，和当前 `/fsm` 契约不一致。

### 5.3 FR4 用例要并入后续链路

当前主流程在进入 FR5 之前会把 FR3 和 FR4 用例合并后再送进 Oracle。

如果后端采用分步接口方式，也建议保持同样策略：

- FR3 的 `/generate` 产物写入 `test_cases`
- FR4 的 `/fsm` 产物也写入 `test_cases`
- 通过 `technique == "FSM"` 或额外的 `test_source` 区分来源

这样 `/oracle`、`/optimize`、`/export` 不需要再额外区分一套 `fsm_test_cases` 存储。

## 6. 建议的改造顺序

建议按下面顺序接，改动最平滑：

1. 先把 `coverage_strategy/service.py` 的 `/coverage`、`/strategy` 改成直连 `AgentPipeline`
2. 再把 `test_design/service.py` 的 `/generate` 改成直连 `AgentPipeline.generate_tests(...)`
3. 再把 `test_design/service.py` 的 `/fsm` 改成直连 `AgentPipeline.generate_fsm(...)`
4. 复用 `/oracle` 现有写法，把 FR4 用例并入 `test_cases`
5. 最后再决定是否需要新增一个统一 SSE 接口去包 `generate_blackbox_tests_stream(...)`

## 7. 验收清单

接入完成后，至少要确认下面几件事：

- `/coverage` 不再返回空 `coverage_goals`
- `/strategy` 不再返回空 `coverage_items`
- `/generate` 不再返回空 `test_design_specs` 和 `test_cases`
- `/fsm` 不再返回空 `fsm`，并且 `fsm.transitions[*].from` 字段存在
- `/fsm` 返回的所有用例 `technique == "FSM"`
- `/oracle` 能同时接收 FR3 和 FR4 用例
- `/optimize`、`/export` 能消费包含 FSM 用例的 `test_cases`

建议重点回归：

- `Testing/tests/test_runner_fr45_orchestration.py`
- `Testing/tests/test_fsm_api.py`

其中 `test_fsm_api.py` 体现的是目标契约；在当前 app 层未接通前，这组测试和现状是不一致的，接完 FR4 后应优先修回到通过状态。

## 8. 一句话总结

**FR3/FR4 不需要再重写一套后端逻辑，直接把 app 层空 service 接到 `backend/agent` 现成的 `AgentPipeline` / runner 上就够了。**
