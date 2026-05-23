# AutoTestDesign Backend

## 架构概览

后端按**交付边界**拆为三个 Python 包，三层在**同一个进程**内运行，通过**函数调用**直接对接（不是 HTTP，不是 RPC）。

```
┌──────────────────────────────────────────────────┐
│              uvicorn 启动的单一进程                │
│                                                  │
│  ┌──────────┐    import     ┌──────────────────┐ │
│  │   app/   │ ────────────► │     agent/       │ │
│  │  Web 层  │               │   AI 编排层      │ │
│  │          │ ◄──────────── │                  │ │
│  │ HTTP ↕   │    返回值      │  内部 import     │ │
│  │ 前端     │               │      │           │ │
│  └──────────┘               │      ▼           │ │
│       │                     │  ┌──────────┐    │ │
│       │     import          │  │   rag/   │    │ │
│       └─────────────────────┼──► 检索层   │    │ │
│                             │  └──────────┘    │ │
│                             └──────────────────┘ │
└──────────────────────────────────────────────────┘
```

```
backend/
├── main.py                         # FastAPI 入口
│
├── app/                            # ① Web 层 — 对外面向前端，对内调 agent/rag
│   ├── core/                       #     配置、异常、依赖注入
│   ├── common/                     #     跨模块公共类型与基类
│   └── modules/                    #     按前端工作流步骤拆的功能模块
│       ├── health/                 #        健康检查
│       ├── requirements/           #        Step1: 需求摄入与解析
│       ├── analysis/               #        Step2: 风险分析与覆盖设计
│       ├── generation/             #        Step3: 用例生成 + FSM + Oracle
│       └── exports/                #        Step4: 套件优化与导出
│
├── agent/                          # ② AI 编排层 — 所有 LLM 调用、Prompt 管理
│
└── rag/                            # ③ 检索层 — 文档向量化、语义检索
```

---

## 三层职责

### app/ — Web 层（你对前端暴露的 HTTP 接口）

**只做三件事：**

1. 接收前端请求（文件、JSON body）
2. 调用 `agent/` 或 `rag/` 的公开接口处理数据
3. 把处理结果返回给前端

**不允许做的事：**

- 拼接 prompt、调用 LLM API
- 操作向量数据库、做 embedding
- 写业务逻辑

每个模块的固定结构：

```
modules/requirements/
├── router.py       # HTTP 路由，校验输入 → 调 service → 返回响应
├── schemas.py      # 请求/响应 Pydantic 模型（前端契约，不可随意改）
└── service.py      # 薄编排层，组合调用 agent/rag 的接口
```

**为什么没有 models.py？** 领域模型不属于 app 层。`agent/` 输出什么结构、`rag/` 内部用什么表示，那是它们自己的事。app 只需要 schemas（API 契约）。

#### 当前 API 端点

| 端点 | 模块 | 前端对应步骤 |
|---|---|---|
| `GET  /health` | health | — |
| `POST /ingest` | requirements | Step1 输入需求文本 |
| `POST /parse` | requirements | Step1 解析需求结构 |
| `POST /risk` | analysis | Step2 风险分析 |
| `POST /coverage` | analysis | Step2 覆盖项生成 |
| `POST /generate` | generation | Step3 用例生成 |
| `POST /fsm` | generation | Step3 状态机模型 |
| `POST /oracle` | generation | Step3 用例质量评估 |
| `POST /optimize` | exports | Step4 套件精简 |
| `POST /export` | exports | Step4 导出文件 |

---

### agent/ — AI 编排层

**负责所有与 LLM 交互的逻辑：**

- 管理 prompt 模板
- 调用 LLM API（OpenAI / 本地模型）
- 解析 LLM 输出为结构化数据
- 多步骤推理编排（规划 → 生成 → 验证 → 优化）

**app 只依赖 agent 的公开接口**，不关心内部实现。换模型、改 prompt 只在 `agent/` 内发生，app 层无感知。

当前的接口设计（后续实现）：

```python
# agent/ 对外暴露的函数签名示例
def parse_requirements(text: str) -> list[ParsedRequirement]: ...
def analyze_risk(requirements: list[Requirement]) -> list[RiskResult]: ...
def generate_testcases(requirements: list[Requirement],
                        coverage_items: list[CoverageItem]) -> list[TestCase]: ...
def build_fsm(requirements: list[Requirement]) -> FSMResult: ...
def evaluate_oracle(test_cases: list[TestCase]) -> list[OracleResult]: ...
def optimize_suite(test_cases: list[TestCase],
                    mode: str) -> OptimizeResult: ...
```

---

### rag/ — 检索层

**负责所有与向量检索相关的逻辑：**

- 文档摄入与切分
- 文本 embedding 与向量存储
- 语义检索
- 检索结果格式化（给 agent 当上下文用）

**独立于 app 和 agent**。如果需要切换向量数据库（ChromaDB → Milvus），只改 `rag/` 内部。

当前的接口设计（后续实现）：

```python
# rag/ 对外暴露的函数签名示例
def index_documents(docs: list[Document]) -> None: ...
def search(query: str, top_k: int = 5) -> list[SearchResult]: ...
```

---

## 依赖方向（同进程 import，非 HTTP）

```
app/                  agent/
┌──────────┐         ┌──────────────┐
│ service.py│──import──► generate_testcases()
│          │         │              │
│          │──import──► search()    │
└──────────┘         │      │       │
                     │      ▼       │
                     │  ┌───────┐   │
                     │  │ rag/  │◄──┤── import
                     │  └───────┘   │
                     └──────────────┘

❌ 禁止反向：agent/ 不能 import app/
❌ 禁止 app/ 直接 import agent/rag/ 的内部实现文件（只调公开接口）
```

- 三层打包到同一个容器里，`app/` 通过 `from backend.agent.xxx import yyy` 直接调用函数
- `agent/` 和 `rag/` 不需要启动 HTTP 服务，不需要额外的端口
- 对外暴露给前端的只有 `app/` 这一个 HTTP 入口

---

## 数据流（以 Step3 生成用例为例）

```
React 前端
  │  POST /generate  { requirement_ids: [...], coverage_items: [...] }
  ▼
app/modules/generation/router.py
  │  校验请求正文 (schemas.py)
  ▼
app/modules/generation/service.py
  │  ┌─ rag.search(requirement_text)     ← 检索相关上下文
  │  └─ agent.generate_testcases(...)    ← LLM 生成用例
  ▼
  │ 组装结果，返回 JSON
  ▼
React 前端收到 [TestCase, TestCase, ...]
```

app 的 service 只做三步：**调 rag → 调 agent → 组装结果**。没有任何自己的逻辑。

---

## 配置

`app/core/config.py` 从项目根目录的 `.env` 或 `backend/.env` 读取配置。

关键变量：

| 变量 | 用途 |
|---|---|
| `API_HOST` / `API_PORT` | 服务监听地址 |
| `CORS_ORIGINS` | 允许的前端域名 |
| `OPENAI_API_KEY` | LLM API Key（agent 层用） |
| `AGENT_BASE_URL` | 自部署模型的 URL（可选） |
| `RAG_ENABLED` | 是否启用 RAG 增强 |

---

## 本地运行

```bash
cd backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

API 文档：`http://localhost:8000/docs`

---

## 给新组员的开发指引

**你要加一个新接口？**

1. 确定属于哪个前端步骤 → 找到对应 `modules/<模块>/`
2. 在 `schemas.py` 定义请求/响应模型
3. 在 `service.py` 写编排逻辑（调 agent/rag）
4. 在 `router.py` 加路由
5. 在 `main.py` 注册 router

**你要写 AI 逻辑？**

在 `agent/` 下新建文件，定义公开函数。然后在 `app/modules/<模块>/service.py` 里调用它。

**你要写检索逻辑？**

在 `rag/` 下新建文件，定义公开函数。然后在需要检索的 service 或 agent 里调用它。

**一句话记住：app 是门面，agent 是大脑，rag 是知识库。**
