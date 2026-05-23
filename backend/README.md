# AutoTestDesign Backend

This backend follows a typical small FastAPI layout. The `app/` package is the frontend-facing backend owned by the backend/frontend integration role.

## Ownership Boundaries

```text
backend/
|-- main.py                      # FastAPI entrypoint
|-- app/                         # Owned area: frontend/backend interaction
|   |-- api/
|   |   |-- router.py            # Collects route modules
|   |   `-- routes/              # FastAPI route handlers
|   |-- core/                    # Global config and bootstrap helpers
|   |-- schemas/                 # Request/response Pydantic models
|   |-- models/                  # Internal domain models
|   `-- services/                # Application services
|-- rag/                         # RAG owner boundary, placeholder only for now
`-- agent_algorithm/             # Agent/algorithm owner boundary, placeholder only for now
```

RAG and Agent functionality is intentionally not implemented inside `app/`.
Frontend-facing services contain single-line `TODO(RAG)` or `TODO(Agent)` comments where those modules will be connected later.

## Configuration

Settings are loaded globally from `.env` in the repository root or `backend/.env`.
Use `backend/.env.example` as the template.

Important variables:

- `API_HOST`
- `API_PORT`
- `CORS_ORIGINS`
- `OPENAI_API_KEY`
- `AGENT_BASE_URL`
- `RAG_ENABLED`

## Run

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

API docs:

```text
http://localhost:8000/docs
```

## Frontend Contract Endpoints

- `GET /health`
- `GET /dashboard`
- `POST /ingest`
- `POST /parse`
- `POST /risk`
- `POST /coverage`
- `POST /fsm`
- `POST /generate`
- `POST /oracle`
- `POST /optimize`
- `POST /export`
- `GET /export/{json|csv|xlsx}`
- `GET /review/history`
- `POST /review/revise`
- `POST /review/regenerate`

All frontend endpoints are registered. Endpoints whose owners are RAG or Agent return empty or no-op results until those modules are connected.
