"""Frontend-facing HTTP layer.

This package is a thin proxy:
- Receives requests/files from the React frontend
- Delegates all processing to `agent/` (AI orchestration) and `rag/` (retrieval)
- Returns structured responses

No business logic, no AI logic, no vector logic lives here.
"""
