# AutoTestDesign 后端说明

本后端只负责 AutoTestDesign 测试设计工具本身，不实现 AUT 的图书馆业务 API。

后端职责包括：

- 需求输入与样例需求读取
- 需求解析
- 风险分析
- 覆盖项生成
- 测试用例生成
- Interactive Review 修改记录
- RAG 标准文档检索预留
- JSON / CSV / XLSX 导出

LibraryManagementSystem 是被测对象（AUT），它的 `books / members / borrow / return` 业务接口不属于本工具后端。

## 目录结构

```text
backend/
├─ main.py                  # FastAPI 入口，直接创建 app
├─ requirements.txt
├─ README.md
├─ models.py                # 当前所有 Pydantic 模型集中放这里
├─ routers/
│  ├─ design.py             # ingest / parse / risk / coverage / generate
│  ├─ review.py             # Interactive Review 修改记录
│  └─ export.py             # json / csv / xlsx 导出
├─ services/
│  ├─ parsing.py            # 需求导入与解析
│  ├─ risk.py               # 风险分析
│  ├─ coverage.py           # 覆盖项生成
│  ├─ generation.py         # 测试用例生成
│  ├─ review.py             # 修改记录管理
│  └─ exporting.py          # 导出逻辑
├─ rag_engine/
│  ├─ ingest.py             # 标准文档入库
│  ├─ retrieve.py           # 检索测试标准片段
│  ├─ vector_store.py       # ChromaDB 封装
│  └─ prompt_builder.py     # 拼接 Prompt
├─ data/
│  ├─ standards/            # ISTQB / ISO 29119 等测试标准文档
│  └─ samples/              # AUT SRS / 15 条需求样例
└─ chroma_db/               # ChromaDB 持久化目录
```

## 安装与启动

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

API 文档：

```text
http://localhost:8000/docs
```

健康检查：

```text
GET http://localhost:8000/health
```

## 当前可用接口

测试设计主流程：

- `POST /ingest`
- `POST /parse`
- `POST /risk`
- `POST /coverage`
- `POST /generate`

Interactive Review：

- `GET /review/history`
- `POST /review/revise`
- `POST /review/regenerate`

导出：

- `POST /export/json`
- `POST /export/csv`
- `POST /export/xlsx`

## 当前 stub 状态

- 需求解析是确定性规则，尚未接真实 LLM。
- 风险分析基于样例优先级，尚未接 RAG 风险依据。
- 覆盖项和测试用例生成是稳定 stub，后续可接 EP / BVA / DT / FSM 算法。
- Interactive Review 使用内存列表保存历史，重启后会清空。
- RAG 已预留 ChromaDB 入库、检索和 Prompt 构建接口，但尚未接完整评测流程。

## 样例需求加载

`POST /ingest` 不会再因为空输入自动加载样例，避免误吞真实输入错误。

需要加载 15 条课程样例时，请显式传入：

```json
{
  "source_type": "sample",
  "content": ""
}
```

## RAG 后续开发位置

成员 B 后续从这里继续：

```text
backend/rag_engine/
```

建议顺序：

1. 把测试标准文档放入 `backend/data/standards/`
2. 调用 `backend/rag_engine/ingest.py` 入库
3. 在 `backend/rag_engine/retrieve.py` 中调优检索
4. 在 `backend/rag_engine/prompt_builder.py` 中维护 parse / risk / generate / oracle prompt
5. 由 `backend/services/parsing.py`、`backend/services/risk.py`、`backend/services/generation.py` 调用 RAG 能力

## 标准文档放置方式

把 `.txt`、`.md` 或 `.pdf` 标准文档放到：

```text
backend/data/standards/
```

当前 PDF 读取使用 `pymupdf`，向量库存放在 `backend/chroma_db/`。
