# AutoTestDesign

AutoTestDesign is a course project for the 2026 Spring Software Testing course at Tongji University. It is an AI-assisted software test design prototype for requirement parsing, risk analysis, test case generation, test oracle support, artifact export, and test suite optimization.

This repository currently contains only the initial project scaffold. Implementation details will be added later according to the team role split.

## Repository Layout

```text
.
├── algorithm/
│   └── PLACEHOLDER.md
├── backend/
│   └── PLACEHOLDER.md
├── frontend/
│   └── PLACEHOLDER.md
├── tests/
│   └── PLACEHOLDER.md
├── localDocs/          # local-only course/reference documents, ignored by git
├── .gitignore
└── README.md
```

## Planned Modules

| Directory | Purpose |
|---|---|
| `frontend/` | Frontend application source code |
| `backend/` | Backend service source code and API implementation |
| `algorithm/` | Test design algorithms and suite optimization logic |
| `tests/` | Unit tests, integration tests, RAGAS evaluation, and submission checks |

## Role Split

| Role | Responsibility |
|---|---|
| A | Backend lead: FastAPI, input API, FSM, export, and NFR hardening |
| B | AI/RAG lead: knowledge base, retrieval, prompts, risk engine, and Oracle |
| C | Frontend/UX lead: UI, heatmap, test case table, FSM visualization, and UX polish |
| D | Test/Integration/Doc lead: pytest, AUT SRS samples, RAGAS, A/B, README, and submission QA |
| E | Algorithm/backend engineer: EP/BVA/DT generators and suite optimization |

## Git Notes

`localDocs/` is intentionally excluded from version control because it contains local course materials and working documents. Do not upload it to the remote repository.

## Current Status

- Minimal project architecture created.
- `frontend/`, `backend/`, `algorithm/`, and `tests/` each contain one placeholder file.
- Detailed implementation will be added in later development steps.
