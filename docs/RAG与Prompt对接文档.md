# RAG 与 Prompt 对接文档

## 1. 文档目标

本文档面向 B RAG、LLM 与 Prompt 负责人，用于明确 RAG 和 Prompt 需要完成什么工作，如何向后端和算法提供结果，以及如何完成 AUT 风险评估。

B 的职责是语义理解、知识检索、Prompt 设计、风险评分、Oracle 和 Prompt 透明化。B 不负责前端展示，不负责后端 endpoint 实现，也不负责确定性算法。

## 2. RAG 知识来源

RAG 至少应支持以下知识来源：

| 来源 | 用途 |
|---|---|
| AUT SRS | 提供 `LibraryManagementSystem` 的需求背景 |
| 15-sample requirement set | 用于解析、风险评分和测试设计验证 |
| ISTQB 或测试理论资料 | 支持 EP、BVA、DT、FSM、Oracle 的测试方法依据 |
| ISO/IEC/IEEE 29119 相关资料 | 支持测试过程、测试设计和文档标准依据 |
| 已生成的 RevisionRecord | 支持差量再生成和基于证据的改进 |

RAG 返回的上下文必须保留 `source_context_ids`，供 PromptEvidence 记录和 D 验收。

## 3. RAG 基本流程

```text
输入查询
-> 识别任务类型
-> 检索相关 AUT 需求和测试标准
-> 过滤无关上下文
-> 组织 Prompt 输入
-> 调用 LLM
-> 输出结构化 JSON
-> 保存 PromptEvidence
```

RAG 输出不应直接作为最终测试用例。最终测试用例由 E 的算法和后端编排共同形成。

## 4. Prompt 模板清单

| Prompt 模板 | 触发接口 | 输入 | 输出 | 消费方 |
|---|---|---|---|---|
| requirement_parse | `/parse` | Requirement、RAG 上下文 | ParsedRequirement | A、C、D、E |
| concept_identification | `/concepts` | Requirement、ParsedRequirement、RAG 上下文 | Concept | A、C、D、E |
| risk_scoring | `/risk` | Requirement 或 CoverageItem、风险矩阵、RAG 证据 | RiskResult | A、C、D、E |
| coverage_identification | `/coverage` | ParsedRequirement、Concept、RiskResult | 候选 CoverageItem | A、E、C、D |
| strategy_assignment | `/strategy` | CoverageItem、RiskResult、测试标准上下文 | Strategy 建议 | A、E、C、D |
| test_case_draft | `/generate` | CoverageItem、Strategy、ParsedRequirement | 测试用例草案和解释 | A、E |
| oracle_review | `/oracle` | TestCase、Requirement、RAG 上下文 | expected_result 建议 | A、C、D |
| revision_regeneration | `/regenerate` | RevisionRecord、当前设计状态 | 受影响项说明和再生成建议 | A、E、C、D |

每个 Prompt 模板都必须要求模型输出 JSON，不允许只输出自然语言段落。

## 5. 结构化解析任务

`requirement_parse` 必须从 AUT requirement 中抽取：

```json
{
  "requirement_id": "REQ-AUT-*",
  "input_fields": [],
  "data_ranges": [],
  "conditions": [],
  "expected_action": "",
  "confidence": 0.0
}
```

解析结果供 E 的 EP、BVA、DT 和 FSM 使用。如果字段不明确，应输出低置信度并给出缺失原因，不能编造范围。

## 6. 覆盖项识别任务

`coverage_identification` 输出候选覆盖项，重点覆盖：

- 正常业务路径；
- 输入边界；
- 无效输入；
- 错误路径；
- 条件组合；
- 状态迁移；
- 高风险需求。

候选覆盖项由 E 进行去重、编号和结构化，B 不负责最终 `coverage_item_id` 分配。

## 7. 覆盖策略建议任务

`strategy_assignment` 需要为每个覆盖项建议测试技术：

| 覆盖项类型 | 推荐技术 |
|---|---|
| 输入有效/无效分类 | EP |
| 数值、日期、长度、库存边界 | BVA |
| 多条件业务规则 | DT |
| 借阅、归还等状态变化 | FSM |

输出必须包含 `standard_ref` 和选择理由，供 D 验证策略合理性。

## 8. 风险评估任务

风险评分对象只能是：

- `REQ-AUT-*`
- `FR-AUT-*`
- `COV-AUT-*`

不得对成员任务、工具模块或实现难度打风险分。

### 8.1 风险评分字段

```json
{
  "target_id": "REQ-AUT-*",
  "target_type": "requirement | coverage_item",
  "impact": 1,
  "likelihood": 1,
  "risk_score": 1,
  "risk_level": "Low | Medium | High",
  "test_priority": "P1 | P2 | P3",
  "reason": "",
  "evidence": []
}
```

### 8.2 建议评分规则

| 分数 | Impact | Likelihood |
|---|---|---|
| 1 | 影响很小，不影响核心借阅流程 | 很少发生 |
| 2 | 影响局部功能 | 偶尔发生 |
| 3 | 影响一个主要业务功能 | 可能发生 |
| 4 | 影响借书、还书等核心流程 | 较常发生 |
| 5 | 可能导致核心流程不可用或数据严重错误 | 高概率发生 |

建议风险等级：

| Risk Score | Risk Level | Test Priority |
|---|---|---|
| 1-6 | Low | P3 |
| 7-14 | Medium | P2 |
| 15-25 | High | P1 |

## 9. 给算法的调用契约

B 不直接调用 E 的算法。推荐由后端按以下顺序编排：

```text
B 输出语义候选
-> 后端校验和保存 PromptEvidence
-> E 进行确定性生成或规范化
-> 后端合并结果
-> 必要时 B 再做 Oracle 或解释补充
```

| E 需要的内容 | B 提供方式 |
|---|---|
| 输入字段和范围 | `requirement_parse` 输出 |
| 条件和业务规则 | `requirement_parse` 与 `concept_identification` 输出 |
| 覆盖项候选 | `coverage_identification` 输出 |
| 测试技术建议 | `strategy_assignment` 输出 |
| 标准依据 | RAG 上下文和 `standard_ref` |
| 期望结果解释 | `oracle_review` 输出 |
| 修订影响说明 | `revision_regeneration` 输出 |

## 10. PromptEvidence 要求

每次 LLM 参与都必须保存：

```json
{
  "prompt_template_id": "PROMPT-*",
  "requirement_id": "REQ-AUT-*",
  "prompt_inputs": {},
  "source_context_ids": [],
  "model_name": "",
  "output_schema_version": "",
  "output_summary": ""
}
```

前端需要展示 PromptEvidence，D 需要用它证明 Prompt 设计和结果分析真实发生。

## 11. RAGAS 与 A/B 对比

B 需要提供给 D：

- golden QA set；
- RAG 输出样本；
- plain LLM 输出样本；
- RAG-enhanced 输出样本；
- hallucination case 列表；
- invalid `standard_ref` 列表。

D 负责运行或汇总 RAGAS 和 A/B 结果，B 负责根据结果调整 RAG 和 Prompt。

