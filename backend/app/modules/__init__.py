"""Feature modules — each maps to a frontend workflow step.

Every module follows the same structure:
- router.py   → HTTP routes (validates input, calls service, returns response)
- schemas.py  → Request/Response Pydantic models (API contract)
- service.py  → Thin orchestration (delegates to agent/rag layers)
"""
