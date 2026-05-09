# 分支与质量门禁规则

## 分支流程

- `main` 是受保护的发布分支。
- `develop` 是受保护的集成分支。
- 功能开发应使用短生命周期分支，例如 `feat/test`、`feat/frontend`、`fix/backend-build` 或 `docs/test-plan`。
- 合并到 `main` 的 Pull Request 只能来自 `develop`。
- 合并到 `develop` 的 Pull Request 可以来自功能、修复、测试或文档分支。
- GitHub 分支保护中应禁止直接推送到 `main` 和 `develop`。

## GitHub Issues

本项目不强制要求 Pull Request 关联 GitHub Issue。

当某个任务需要明确的进度跟踪、负责人、讨论记录或历史依据时，可以创建 Issue。Pull Request 可以引用 Issue，但 CI 不会因为没有关联 Issue 而失败。

## 必须通过的 CI 门禁

`Project Quality Gate` 工作流会在提交到 `main` 和 `develop` 的 Pull Request 上运行。

必须通过的检查包括：

- `PR Policy Gate`：检查分支流向，并阻止 `localDocs/` 或 `external/` 被提交到 Pull Request。
- `Conditional Builds`：当 `frontend/package.json` 存在时构建前端；当后端存在受支持的构建描述文件时构建后端。
- `Python Test Suite`：运行可在 CI 中稳定复现的 pytest 测试，不包含 live AUT、RAGAS 或 live LLM 凭据相关测试。
- `RAGAS Gate`：仅当 pytest 文件中存在 `@pytest.mark.ragas` 标记的测试时运行；否则正常跳过。

## AUT API 测试规则

AUT 是外部 Spring Boot 项目，不提交到本仓库。

live AUT API 测试维护在 `tests/aut/` 下。当 D 角色修改 AUT API 测试资产时，应在本地启动 AUT 后运行：

```bash
pytest -m aut_api
```

默认 AUT 地址为：

```bash
http://localhost:8080
```

如需使用其他端口，可通过环境变量覆盖：

```bash
AUT_BASE_URL=http://localhost:8081 pytest -m aut_api
```

这些 live 测试不作为 GitHub Actions 的强制门禁，因为 CI 环境不负责启动和维护外部 AUT 运行时。

## GitHub 分支保护设置

分别为 `main` 和 `develop` 创建分支保护规则：

- 要求通过 Pull Request 合并。
- 如果团队规模允许，要求至少一名成员审批。
- 要求合并前通过 status checks。
- 要求合并前分支与目标分支保持最新。
- 要求所有会话被 resolved 后才能合并。
- 禁止 force push。
- 禁止删除受保护分支。

对 `main` 分支，选择了以下 required checks：

- `PR Policy Gate`
- `Conditional Builds`
- `Python Test Suite`
- `RAGAS Gate`

对 `develop` 分支，选择了相同的 required checks。

这些检查名称需要在 GitHub Actions 至少运行一次后，才会出现在 GitHub 分支保护设置的可选列表中。
