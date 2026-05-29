# revision_runner rerun 优化设计

## 背景

`backend/agent/revision_runner.py` 当前承担了过多职责，尤其是 rerun 相关逻辑：

- 每个 reentry stage 都单独手写一套流程。
- `generate`、`fsm`、`oracle`、`strategy`、`risk`、`parse` 之间存在大量重复代码。
- 重复逻辑包括调用 `AgentPipeline`、序列化结果、标记 revision、区分 created/updated、生成 prompt evidence、废弃被替换用例等。
- 文件长度超过 1000 行，后续新增阶段或调整输出格式时容易漏改。

本优化不追求大规模架构拆分，重点是减少 rerun 部分重复代码，让 stage 函数只保留各自真正不同的输入构造逻辑。

## 优化目标

1. 保持对外入口不变：

   ```python
   regenerate_from_revision(revision, current_state, rag_context=None)
   ```

2. 不修改接口响应结构：

   ```python
   {
       "created": {},
       "updated": {},
       "unchanged": {},
       "deprecated": {},
       "prompt_evidence": [],
   }
   ```

3. 不改变现有 prompt 和 LLM 输出协议。
4. 将 rerun 公共流程抽出来，提高复用。
5. 控制拆分规模，整体拆成 3 到 5 个文件即可。

## 非目标

- 不重写完整 AgentPipeline。
- 不引入复杂框架或过度抽象。
- 不把所有 helper 都类化。
- 不在第一轮优化中改变 revision 影响判定策略。
- 不改变前端、API schema、workflow store 的调用方式。

## 建议文件结构

推荐拆成 4 个文件：

```text
backend/agent/revision_runner.py
backend/agent/revision_impact.py
backend/agent/revision_reentry.py
backend/agent/revision_utils.py
```

职责划分：

| 文件 | 职责 |
|---|---|
| `revision_runner.py` | 保留公开入口、总编排、错误类型 |
| `revision_impact.py` | revision 初始影响分析、affected ids、related/selected 查询 |
| `revision_reentry.py` | rerun stage 分发、公共执行器、各 stage 的 rerun 函数 |
| `revision_utils.py` | `ChangeSet`、model dump、evidence、merge、字符串列表等纯工具 |

如果希望更保守，也可以先只拆 3 个文件，把 `revision_impact.py` 和 `revision_utils.py` 合并为 `revision_support.py`。但从可读性看，4 个文件更合适。

## 核心设计

### 1. 引入 ReentryContext

`ReentryContext` 保存 rerun 过程中反复传递的上下文，减少函数参数数量。

```python
@dataclass
class ReentryContext:
    revision: dict[str, Any]
    state: dict[str, list[dict[str, Any]]]
    impact: dict[str, Any]
    impacted_coverage: list[dict[str, Any]]
    impacted_tests: list[dict[str, Any]]
    current_state: dict[str, Any] | None
    rag_context: str | None
    pipeline: AgentPipeline

    @property
    def session_id(self) -> str:
        return str(self.revision.get("session_id") or "")

    @property
    def revision_id(self) -> str:
        return str(self.revision.get("revision_id") or "")

    @property
    def effective_rag_context(self) -> str:
        return self.rag_context or str((self.current_state or {}).get("rag_context") or "")
```

收益：

- 原来每个 `_rerun_from_xxx` 都传 6 到 7 个参数。
- 改成传 `ctx` 后，函数签名更短。
- stage 间复用状态更自然。

### 2. 引入 ChangeSet

当前 created、updated、deprecated 到处用 dict 手动合并。建议增加一个轻量 `ChangeSet`。

```python
@dataclass
class ChangeSet:
    created: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    updated: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    deprecated: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def add_created(self, collection: str, items: list[dict[str, Any]]) -> None: ...
    def add_updated(self, collection: str, items: list[dict[str, Any]]) -> None: ...
    def add_deprecated(self, collection: str, items: list[dict[str, Any]]) -> None: ...
    def merge(self, other: "ChangeSet") -> None: ...
```

收益：

- `_merge_grouped`、`_add_group` 的使用位置减少。
- handler 只关心“这批结果属于哪个 collection”。
- 最终 response 统一从 `ChangeSet` 导出。

### 3. 用 OutputSpec 描述 stage 输出

很多 stage 的输出处理方式完全一样：

1. 从 pipeline result 中取某个字段。
2. `model_dump` 成 dict。
3. 打 revision 标记。
4. 与已有 state 对比，分成 created / updated。
5. 写入 ChangeSet。

可以用 `OutputSpec` 描述这件事。

```python
@dataclass(frozen=True)
class OutputSpec:
    collection: str
    attr: str
    id_field: str
    mode: Literal["split", "update"] = "split"
    mark_revision: bool = True
```

示例：

```python
OutputSpec(
    collection="test_cases",
    attr="test_cases",
    id_field="test_id",
    mode="split",
)
```

`mode` 说明：

- `split`：根据 id 判断 created / updated。
- `update`：全部放入 updated，适合 oracle results 这类覆盖更新。

### 4. 抽通用 pipeline step 执行器

核心复用点是 `run_pipeline_step`。

```python
async def run_pipeline_step(
    ctx: ReentryContext,
    stage: str,
    call: Callable[[], Awaitable[Any]],
    outputs: list[OutputSpec],
    evidence_summary: Callable[[Any, ChangeSet], dict[str, Any]],
) -> ReentryResult:
    result = await call()
    changes = ChangeSet()

    for spec in outputs:
        items = model_dump_list(getattr(result, spec.attr))
        if spec.mark_revision:
            mark_revision(items, ctx.revision, "pipeline_regenerated")

        if spec.mode == "update":
            changes.add_updated(spec.collection, items)
        else:
            created, updated = split_created_updated(
                items,
                ctx.state.get(spec.collection, []),
                spec.id_field,
            )
            changes.add_created(spec.collection, created)
            changes.add_updated(spec.collection, updated)

    evidence = agent_prompt_records_to_evidence(
        ctx.session_id,
        result.prompts_used,
        ctx.revision_id,
        evidence_summary(result, changes),
        f"Revision re-entered AgentPipeline.{stage}.",
    )
    return ReentryResult(changes=changes, evidence=evidence)
```

`ReentryResult` 可以很轻：

```python
@dataclass
class ReentryResult:
    changes: ChangeSet = field(default_factory=ChangeSet)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def merge(self, other: "ReentryResult") -> None: ...
```

## stage 函数改造示例

### oracle rerun

优化前的问题：

- 自己选 test cases。
- 自己调用 pipeline。
- 自己 dump。
- 自己 mark。
- 自己构造 updated。
- 自己写 evidence。

优化后：

```python
async def rerun_oracle(ctx: ReentryContext) -> ReentryResult:
    test_cases = ctx.impacted_tests or selected_test_cases(ctx.impact, ctx.state)
    if not test_cases:
        raise RevisionRunnerError("oracle reentry requires at least one affected test case", 422)

    return await run_pipeline_step(
        ctx,
        stage="generate_oracles",
        call=lambda: ctx.pipeline.generate_oracles(
            test_cases,
            requirements=related_requirements(ctx.state, ctx.revision, [], test_cases),
            rag_context=ctx.effective_rag_context,
        ),
        outputs=[
            OutputSpec(
                collection="oracle_results",
                attr="oracle_results",
                id_field="test_id",
                mode="update",
            )
        ],
        evidence_summary=lambda result, changes: {
            "stage": "oracle",
            "oracle_result_count": len(result.oracle_results),
        },
    )
```

### generate rerun

`generate` 的业务差异是需要拆分 EP/BVA/DT 和 FSM。公共输出处理仍然复用。

```python
async def rerun_generate(ctx: ReentryContext) -> ReentryResult:
    coverage_items = selected_coverage_items(ctx.impact, ctx.state, ctx.impacted_coverage)
    normal_items = [item for item in coverage_items if coverage_technique(item) != "FSM"]
    fsm_items = [item for item in coverage_items if coverage_technique(item) == "FSM"]

    result = ReentryResult()

    if normal_items:
        normal_result = await run_pipeline_step(
            ctx,
            stage="generate_tests",
            call=lambda: ctx.pipeline.generate_tests(
                [agent_coverage_item(item, ctx.state) for item in normal_items],
                agent_risk_items(ctx.state, normal_items),
                ctx.effective_rag_context,
            ),
            outputs=[
                OutputSpec(
                    collection="test_cases",
                    attr="test_cases",
                    id_field="test_id",
                    mode="split",
                )
            ],
            evidence_summary=lambda pipeline_result, changes: {
                "stage": "generate",
                "test_case_count": len(pipeline_result.test_cases),
            },
        )
        result.merge(normal_result)

    if fsm_items:
        fsm_ctx = replace(ctx, impacted_coverage=fsm_items)
        result.merge(await rerun_fsm(fsm_ctx))

    result.changes.add_deprecated(
        "test_cases",
        deprecate_replaced_tests(ctx.impacted_tests, result.changes, ctx.revision),
    )
    return result
```

### fsm rerun

```python
async def rerun_fsm(ctx: ReentryContext) -> ReentryResult:
    coverage_items = ctx.impacted_coverage or selected_coverage_items(ctx.impact, ctx.state, [])

    result = await run_pipeline_step(
        ctx,
        stage="generate_fsm",
        call=lambda: ctx.pipeline.generate_fsm(
            requirements=related_requirements(ctx.state, ctx.revision, coverage_items, ctx.impacted_tests),
            parsed_requirements=ctx.state.get("parsed_requirements", []),
            coverage_items=coverage_items,
            rag_context=ctx.effective_rag_context,
        ),
        outputs=[
            OutputSpec(
                collection="test_cases",
                attr="test_cases",
                id_field="test_id",
                mode="split",
            )
        ],
        evidence_summary=lambda pipeline_result, changes: {
            "stage": "fsm",
            "test_case_count": len(pipeline_result.test_cases),
        },
    )

    fsm_payload = result_fsm_to_dict(...)  # 可封装为工具函数
    result.changes.add_updated("fsm", [fsm_payload])
    result.changes.add_deprecated(
        "test_cases",
        deprecate_replaced_tests(ctx.impacted_tests, result.changes, ctx.revision),
    )
    return result
```

注意：当前 response 里 `fsm` 是对象，不是 list。`ChangeSet` 如果只处理 list collection，则 `fsm` 可以继续由特殊逻辑写入 `updated["fsm"]`。不建议为这个少数情况把 `ChangeSet` 设计得太复杂。

## stage 分发

保留简单字典分发即可，不需要复杂 registry。

```python
RERUNNERS = {
    "parse": rerun_parse,
    "risk": rerun_risk,
    "strategy": rerun_strategy,
    "generate": rerun_generate,
    "fsm": rerun_fsm,
    "oracle": rerun_oracle,
    "analysis": rerun_analysis,
}


async def rerun_from_impact(ctx: ReentryContext) -> ReentryResult:
    stage = str(ctx.impact.get("reentry_stage") or "")
    try:
        rerunner = RERUNNERS[stage]
    except KeyError as exc:
        raise RevisionRunnerError(f"unsupported reentry_stage: {stage}", 502) from exc
    return await rerunner(ctx)
```

## parse/risk/strategy 的复用方式

`parse`、`risk`、`strategy` 本身是链式重跑，不能完全用一个 step 覆盖，但仍然可以复用公共输出处理：

- `risk`：调用 `run_pipeline_step` 生成 risk，再进入 `rerun_strategy`。
- `strategy`：调用 `run_pipeline_step` 生成 coverage items，再进入 `rerun_generate`。
- `parse`：依次调用 parse、risk、coverage、strategy、generate。每一步的输出入库逻辑可以走同一套 `apply_output_specs`，避免手写多个 `_model_dump_list` 和 evidence 循环。

建议第一轮不要强行把 `parse` 压得很短。它天然复杂，先把 `generate/fsm/oracle/strategy/risk` 的重复消掉即可。

## 迁移步骤

### 第一步：增加测试

先补最小行为测试，避免拆分时改坏：

- coverage item 修订后进入 generate。
- FSM coverage item 修订后进入 fsm。
- test case 行为修订后进入 oracle。
- strategy/risk 修订会继续触发下游重跑。
- 新生成 test case 会被标记 `regenerated_from_revision`。
- 被替换的旧 test case 会进入 deprecated。

### 第二步：抽 `revision_utils.py`

先移动纯函数，不改逻辑：

- `_model_dump_list`
- `_to_dicts`
- `_string_list`
- `_dedupe`
- `_dedupe_by_id`
- `_merge_grouped`
- `_mark_revision`
- `_split_created_updated`
- `_prompt_evidence`
- `_agent_prompt_records_to_evidence`
- `_renumber_evidence`
- `_make_next_id`
- `_bounded_int`

这一步风险最低。

### 第三步：抽 `revision_impact.py`

移动影响范围相关函数：

- `_revision_impact`
- `_affected_ids`
- `_mark_related_by_coverage`
- `_impacted_coverage_items`
- `_impacted_test_cases`
- `_has_revision_scope`
- `_selected_coverage_items`
- `_selected_test_cases`
- `_selected_requirements`
- `_related_requirements`
- `_related_risk_results`
- `_related_strategies`

保持函数名和行为不变，先只调整 import。

### 第四步：抽 `revision_reentry.py`

新增：

- `ReentryContext`
- `ReentryResult`
- `OutputSpec`
- `run_pipeline_step`
- `rerun_from_impact`
- `rerun_generate`
- `rerun_fsm`
- `rerun_oracle`
- `rerun_strategy`
- `rerun_risk`
- `rerun_parse`
- `rerun_analysis`

迁移时建议顺序：

1. 先迁移 `oracle`，因为最简单。
2. 再迁移 `fsm`。
3. 再迁移 `generate`。
4. 再迁移 `strategy` 和 `risk`。
5. 最后处理 `parse`。

### 第五步：瘦身 `revision_runner.py`

最终 `revision_runner.py` 只保留：

- `RevisionRunnerError`
- `regenerate_from_revision`
- `_regenerate_impacted_items`
- `_llm_revision_impact`
- `_revision_regenerate_prompt_input`
- `_normalize_revision_impact`
- `_revision_regenerate_evidence`

如果后续还想继续瘦身，可以再把 LLM impact 相关逻辑移动到 `revision_impact.py` 或单独 `revision_llm.py`。第一轮不必强求。

## 验收标准

1. 对外 API 不变。
2. `/regenerate` 响应结构不变。
3. 现有测试全部通过。
4. 新增 revision rerun 单测通过。
5. `revision_runner.py` 明显变短，目标控制在 300 到 500 行。
6. `generate/fsm/oracle` 不再重复手写 evidence、model dump、revision 标记、created/updated split。
7. 修改某个输出处理规则时，只需要改 `run_pipeline_step` 或 `OutputSpec` 相关逻辑。

## 推荐第一轮落地范围

第一轮只做低风险重构：

- 文件拆分。
- 引入 `ReentryContext`。
- 引入 `OutputSpec` 和 `run_pipeline_step`。
- 改造 `oracle`、`fsm`、`generate` 三个 rerun。
- `risk`、`strategy`、`parse` 可以先保持接近原逻辑，只调用新的公共 helper。

这样可以先吃掉最难看的重复代码，同时避免一次性改动太大。

