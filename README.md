# AutoTestDesign

AutoTestDesign is an AI-assisted software test design tool for the 2026 Spring Software Testing course at Tongji University.

The tool supports requirement ingestion, requirement parsing, risk analysis, test design, test case generation, finite state model support, test oracle support, suite optimization, artifact export, and evaluation workflows for software testing activities.

The selected Application Under Test (AUT) for this project is **LibraryManagementSystem**, a Spring Boot REST API application for book, member, borrowing, and return management.

## Main Features

AutoTestDesign provides the following capabilities:

- Requirement ingestion from structured or semi-structured requirement sources.
- Requirement parsing into testable fields, including inputs, data ranges, conditions, and expected actions.
- Risk analysis for AUT requirements.
- Coverage item generation with traceability to AUT requirements.
- Black-box test design support, including Equivalence Partitioning, Boundary Value Analysis, and Decision Table Testing.
- State-based test design support for borrowing and return workflows.
- Test oracle support for checking expected results and response contracts.
- Test case generation with requirement and coverage traceability.
- Human review and revision tracking for interactive test design improvement.
- Test suite optimization and export of test artifacts.
- RAGAS-based evaluation support for RAG-assisted requirement understanding and test design quality.
- pytest-based AUT API testing support.

## Application Under Test

The AUT used by this project is:

```text
LibraryManagementSystem
```

It is tested as an external Spring Boot REST API service.

Default local AUT address:

```text
http://localhost:8080
```

Main AUT API areas:

- Book management
- Member management
- Borrowing records
- Borrowing workflow
- Return workflow
- Error handling

The AUT requirements and test design baseline are documented in:

```text
docs/srs/AUT_SRS_IEEE830_v1.md
tests/data/aut_15_requirements.json
```

## Repository Layout

```text
.
|-- .github/
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
| `frontend/` | Frontend application for the AutoTestDesign workflow |
| `backend/` | Backend service and API implementation |
| `docs/` | Shared AUT requirements, integration contracts, branch policy, and evaluation plans |
| `tests/` | Static artifact checks, AUT API tests, FR1 evaluation helpers, and RAGAS evaluation data |

## Role Split

| Role | Responsibility |
|---|---|
| A | Backend lead: FastAPI gateway, input API, export, integration wrappers, and NFR hardening |
| B | AI/RAG lead: knowledge base, retrieval, prompts, risk engine, and oracle support |
| C | Frontend/UX lead: UI workflow, heatmap, test case table, FSM visualization, and UX polish |
| D | Test/Integration/Documentation lead: pytest, AUT SRS, requirement samples, RAGAS, A/B evaluation, README, and submission QA |
| E | Algorithm/backend engineer: EP/BVA/DT generators, FSM modeling, path coverage, and suite optimization |

## Quality Gate

Pull requests to `main` and `develop` run the `Project Quality Gate` GitHub Actions workflow.

The quality gate includes:

- `PR Policy Gate`: branch flow and local-only directory checks.
- `Conditional Builds`: frontend/backend build checks when the corresponding project exists.
- `Python Test Suite`: CI-safe pytest checks.
- `RAGAS Gate`: conditional RAGAS checks when RAGAS tests are present.

See:

```text
docs/branch_policy.md
```

## Local Test Commands

Install Python test dependencies:

```bash
pip install -r requirements-dev.txt
```

Run CI-safe pytest checks:

```bash
pytest -m "not aut_api and not ragas and not llm" -q
```

Run live AUT API tests after starting LibraryManagementSystem locally:

```bash
pytest -m aut_api -q
```

Use another AUT port if needed:

```bash
AUT_BASE_URL=http://localhost:8081 pytest -m aut_api -q
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Build:

```bash
npm run build
```

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## Documentation

Key shared documents:

| File | Purpose |
|---|---|
| `docs/srs/AUT_SRS_IEEE830_v1.md` | AUT Software Requirements Specification |
| `docs/小组分工_更新版.md` | Role boundaries and cross-role integration ownership |
| `docs/test/testing_framework_rationale.md` | Testing framework rationale |
| `docs/RAGAS/ragas_evaluation_plan.md` | RAGAS evaluation plan |
| `docs/branch_policy.md` | Branch and CI gate policy |
