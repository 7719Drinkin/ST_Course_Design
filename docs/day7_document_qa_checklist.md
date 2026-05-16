# Day7 Document QA Checklist

本文档定义 D 在 Day7 末尾执行的中期文档方向检查。D 只检查方向、格式、占位符和完整性，不替其他成员改写技术内容。

## 1. Core Rule

三份核心文档的描述对象必须是 AUT `LibraryManagementSystem`：

- Risk Analysis Report：AUT 的风险；
- Test Plan：针对 AUT 的测试活动；
- Detailed Test Design：AUT Borrowing 模块的测试设计。

AutoTestDesign 工具架构、RAG pipeline、前端 UI 细节应主要放在 README、演示视频或工具说明中，不应成为三份核心文档的主体。

## 2. Risk Analysis Report Checks

| Section | Owner | Check |
|---|---|---|
| §1 Executive Summary | D | 是否总结 AUT 风险与缓解结果 |
| §2 Risk Identification & Scoring Matrix | B | 是否针对 AUT FR-AUT-* 风险打分 |
| §3 Distribution & Heatmap Visualization | C | heatmap 是否展示 AUT 风险分布 |
| §4 Mitigation Strategies | D | 是否针对 AUT 高风险需求给出测试缓解策略 |

Fail examples:

- 只描述 AutoTestDesign 的开发风险；
- 风险项是“RAG 检索失败”，但没有连接到 AUT 测试影响；
- 没有 impact / likelihood / H-M-L。

## 3. Test Plan Checks

| Section | Owner | Check |
|---|---|---|
| §1 Project Scope | A | 是否说明测试 AUT 的背景和目标 |
| §2.0 AUT Overview | D | 是否说明 AUT baseline |
| §2.1 AUT Architecture | A | 是否描述 AUT Spring Boot / REST / storage |
| §2.2 AUT Functional Features | A/B/E | 是否描述 Book / Member / Borrowing / Records |
| §3 High-Level Test Suite Design | B | 是否基于 AUT 风险选择 EP/BVA/DT/FSM |
| §4 Schedule & Checklist | D | 是否与 updated team assignment 一致 |
| §5 Organization Chart | D | 是否包含 A/B/C/D/E 角色 |
| §6 Testing Framework & Rationale | D | 是否说明 pytest、RAGAS、CI/local gate |
| §7 Cost Estimation | A + D | A 是否填数据，D 是否 review |

Fail examples:

- 章节主体变成 AutoTestDesign 工具架构；
- 没有说明 AUT modules；
- 没有测试对象和测试项。

## 4. Detailed Test Design Checks

| Section | Owner | Check |
|---|---|---|
| §1 Scope | D | 是否聚焦 AUT Borrowing 模块 |
| §1.1 Mainly traceability table | D | 是否记录 coverage -> TC -> prompt -> improvement |
| §2.2 EP Test Cases | B | 是否针对 AUT Borrowing |
| §2.3 BVA Test Cases | B | 是否针对 AUT Borrowing |
| §2.4 Decision Table Test Cases | E | 是否针对 AUT Borrowing |
| §3 White-Box TC Design | A | 是否包含 AUT Borrowing FSM |
| §4 Tool Implementation | D | 是否包含 pytest functions 和执行方式 |
| §5 Results + RAGAS + A/B | D | 是否有真实结果、失败分析、性能分析 |

Fail examples:

- EP/BVA/DT 用例不是 AUT Borrowing；
- 没有 `requirement_id` 或 `test_id`；
- 只展示工具截图，没有测试设计表。

## 5. Placeholder Checks

必须清除：

- `[TODO]`
- `[DATE]`
- `[X]`
- `[score]`
- `[PASS/FAIL]`
- `[screenshot]`
- 空表格
- 空图注
- 未填写 owner

## 6. Feedback Format

D 向 owner 反馈时使用：

```text
Document:
Section:
Owner:
Issue:
Required fix:
Due:
Severity: High / Medium / Low
```

## 7. Day7 Gate Judgment

| Status | Meaning |
|---|---|
| PASS | 三份文档方向正确，无关键 placeholder |
| PARTIAL | 方向基本正确，但存在非阻塞格式/占位问题 |
| FAIL | 多个章节仍描述工具而不是 AUT，或关键章节为空 |
| BLOCKED | D 无法访问共享文档 |
