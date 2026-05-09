# AutoTestDesign

AutoTestDesign is a course project for the 2026 Spring Software Testing course at Tongji University. It is an AI-assisted software test design prototype for requirement parsing, risk analysis, test case generation, test oracle support, artifact export, and test suite optimization.

The current repository contains the shared application scaffold, AUT requirement artifacts, pytest-based API test assets, and GitHub Actions quality gates.

## Repository Layout

```text
.
|-- .github/
|-- algorithm/
|-- backend/
|-- docs/
|-- frontend/
|-- tests/
|-- pytest.ini
|-- requirements-dev.txt
`-- README.md
```

`localDocs/` and `external/` are local-only directories and must not be committed.

## Modules

| Directory | Purpose |
|---|---|
| `frontend/` | Frontend application source code |
| `backend/` | Backend service source code and API implementation |
| `algorithm/` | Test design algorithms and suite optimization logic |
| `docs/` | Shared AUT requirements and project policy documents |
| `tests/` | Static artifact checks, AUT API tests, integration tests, and future RAGAS evaluation tests |

## Role Split

| Role | Responsibility |
|---|---|
| A | Backend lead: FastAPI, input API, FSM, export, and NFR hardening |
| B | AI/RAG lead: knowledge base, retrieval, prompts, risk engine, and Oracle |
| C | Frontend/UX lead: UI, heatmap, test case table, FSM visualization, and UX polish |
| D | Test/Integration/Doc lead: pytest, AUT SRS samples, RAGAS, A/B, README, and submission QA |
| E | Algorithm/backend engineer: EP/BVA/DT generators and suite optimization |

## Quality Gate

Pull requests to `main` and `develop` run the `Project Quality Gate` GitHub Actions workflow.

- `PR Policy Gate`: branch flow and local-only directory checks.
- `Conditional Builds`: frontend/backend build checks when the corresponding project exists.
- `Python Test Suite`: non-live pytest checks that can run in CI.
- `RAGAS Gate`: runs only when pytest files contain tests marked with `@pytest.mark.ragas`.

See `docs/branch_policy.md` for branch protection and test gate details.

## Local Test Commands

Run CI-safe pytest checks:

```bash
pytest -m "not aut_api and not ragas and not llm" -q
```

Run live AUT API tests after starting the AUT locally:

```bash
pytest -m aut_api
```
