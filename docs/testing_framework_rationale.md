# Testing Framework and Rationale

本文档可作为 Test Plan §6 的内容草稿。描述对象是 AUT 的测试活动，不是 AutoTestDesign 工具架构。

## 1. Framework Choice

D 选择 pytest 作为主要测试框架，原因如下：

1. pytest 支持简洁的函数式测试，适合快速编写 REST API 测试。
2. pytest fixtures 适合封装 AUT base URL、HTTP session、测试数据生成器。
3. pytest markers 可以区分 CI-safe tests、live AUT tests、RAGAS tests 和 live LLM tests。
4. pytest 与 GitHub Actions 集成成本低。
5. 后续 EP/BVA/DT 样例可以使用 `@pytest.mark.parametrize` 表达。

## 2. Alternatives

| Tool | Advantage | Limitation in this project |
|---|---|---|
| unittest | Python standard library, no extra dependency | fixture 和参数化能力较弱，表达集成测试较繁琐 |
| Postman | 手工 API 探索方便 | 不适合与 CI、RAGAS、Python 数据处理统一 |
| JUnit | 适合 Java 项目内部测试 | D 的测试资产、RAGAS、A/B 实验均在 Python 侧更容易整合 |
| curl scripts | 简单直接 | 断言、复用、报告和数据驱动能力不足 |

## 3. Current Test Structure

```text
tests/
|-- aut/
|   |-- test_books_api.py
|   |-- test_members_api.py
|   `-- test_borrowing_api.py
|-- data/
|   |-- aut_15_requirements.json
|   `-- ragas_golden_qa_draft.json
|-- conftest.py
`-- test_static_artifacts.py
```

## 4. Marker Strategy

| Marker | Meaning | CI Required |
|---|---|---:|
| `aut_api` | Calls the running external AUT service | no |
| `integration` | Requires multiple modules or running services | no by default |
| `ragas` | Requires RAGAS data, RAG output, and possible model dependencies | conditional |
| `llm` | Requires live LLM or embedding credentials | no |

CI-safe command:

```bash
pytest -m "not aut_api and not ragas and not llm" -q
```

Local AUT regression:

```bash
pytest -m aut_api -q
```

## 5. CI and Local Gate Boundary

CI gate should be deterministic and should not require:

- live AUT on localhost;
- external LLM API key;
- embedding API key;
- manually prepared local data;
- unstable remote model output.

Therefore, GitHub Actions runs:

- static artifact checks;
- frontend build when frontend exists;
- backend build when backend exists;
- RAGAS only when `@pytest.mark.ragas` tests are present.

Live AUT API tests remain a local/manual gate because CI does not own the external Spring Boot runtime.

## 6. RAGAS Position

RAGAS is used to evaluate RAG answer quality for AUT requirement understanding.

Planned metrics:

- answer relevancy;
- faithfulness;
- context precision;
- context recall.

RAGAS will become a meaningful gate only after B provides reproducible RAG answers and retrieved contexts.

## 7. LangSmith Position

LangSmith is useful for tracing RAG / LLM calls:

- prompt input;
- retrieved chunks;
- model output;
- latency;
- failure cases.

In Day3-Day7 it is not a hard dependency. If B enables tracing, D can use trace IDs in FR1 and RAGAS reports.

## 8. Standards Alignment

The AUT test suite aligns with:

| Standard / Body | Usage |
|---|---|
| ISTQB | Defines black-box techniques such as EP, BVA, DT |
| ISO/IEC/IEEE 29119-4 | Provides references for test design techniques |
| IEEE 830 | Structures the AUT SRS baseline |

Generated test cases should include `standard_ref` so that each case can be traced to the relevant testing technique.
