# AutoTestDesign

> AI-Assisted Black-Box Test Design Tool — 同济大学 2026 春《软件测试》课程设计

AutoTestDesign 是一个面向软件测试设计过程的智能化辅助工具。它的目标不是直接替代测试人员，而是帮助测试人员从需求输入开始，逐步完成需求结构化、风险分析、覆盖项识别、覆盖策略选择、测试用例生成、预期结果审查、人工修订、追溯分析和测试套件导出。

工具强调“设计者参与”的测试设计流程。测试人员可以在生成过程中审查、修改和确认关键设计项，并通过修订记录触发后续分析与再生成，使最终测试设计结果具有可解释性、可追溯性和可复核性。

## 核心能力

- 支持文本和常见需求文档上传，提取可用于测试设计的需求内容。
- 将原始需求解析为结构化字段，包括输入字段、数据范围、业务条件、业务规则和期望行为。
- 对需求进行风险分析，输出影响度、发生概率、风险分数、风险等级和测试优先级。
- 识别测试覆盖目标，并为覆盖项选择合适的黑盒测试方法。
- 支持等价类划分、边界值分析、判定表测试和状态迁移相关测试设计。
- 生成测试设计规格和测试用例草案，并保持需求、覆盖项、策略和测试用例之间的追溯关系。
- 生成或审查测试预期结果，标记需要人工复核的用例。
- 支持测试人员对需求、覆盖项、策略和测试用例进行人工修订。
- 根据人工修订记录进行影响分析和相关结果再生成。
- 生成追溯分析结果，展示需求、覆盖项、策略、用例和改进记录之间的映射关系。
- 支持测试套件优化和结构化导出，便于后续编写自动化测试或整理测试文档。
- 提供 RAGAS 评估脚本，用于评估检索增强生成相关证据的质量。

## 工作流程

```text
需求输入
  -> 需求解析
  -> 风险分析
  -> 覆盖项识别
  -> 覆盖策略选择
  -> 测试设计与用例生成
  -> 状态模型与预期结果审查
  -> 人工修订与再生成
  -> 追溯分析
  -> 测试套件优化
  -> 结果导出
```

整个流程围绕测试设计活动展开。工具会在每个阶段保存结构化结果，前端页面负责展示、审查和交互，后端负责接口编排、Agent 调用、数据保存、追溯分析和导出。

## 技术架构

```text
frontend/    前端交互界面，负责需求输入、流程展示、人工审查和结果导出
backend/     后端服务，负责 API、Agent 流水线、RAG、修订、分析和导出
Testing/     测试代码、质量门禁、RAGAS 评估脚本和辅助检查脚本
docs/        项目共享接口文档、流程文档和需求文档
```

## 后端运行

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:create_app --factory --host 127.0.0.1 --port 8000
```

可按需要配置模型调用相关环境变量：

```text
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
RAG_ENABLED=true
```

## 前端运行

```powershell
cd frontend
npm ci
npm run dev
```

前端开发服务默认运行在 `http://127.0.0.1:5173`，后端服务默认运行在 `http://127.0.0.1:8000`。

## 测试

安装测试依赖：

```powershell
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r requirements-dev.txt
```

运行不依赖外部服务的测试：

```powershell
python -m pytest Testing/tests -m "not aut_api and not ragas and not llm" -q
```

运行 RAGAS 评估：

```powershell
python Testing/scripts/run_ragas_evaluation.py --top-k 3 --output-dir Testing/reports
```

## CI/CD

项目使用 GitHub Actions 作为质量门禁，主要检查：

- 仓库治理规则。
- 前端构建是否通过。
- 后端依赖是否可安装。
- 后端应用是否可导入并创建。
- 不依赖外部服务的 pytest 测试是否通过。

需要真实模型调用、真实 RAGAS 评估或外部系统联调的任务，默认作为本地证据生成流程，不作为普通 CI 的强制项。

## 设计目标

AutoTestDesign 的核心目标是让测试设计过程更加结构化、可追溯和可审查。工具生成的结果需要经过测试人员确认，人工修订也会成为后续分析和改进的证据。最终输出不仅包括测试用例，还包括覆盖依据、风险依据、预期结果依据和改进依据。
