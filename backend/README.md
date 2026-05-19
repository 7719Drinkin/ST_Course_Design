# Backend

Flask backend for AutoTestDesign.

## Run

```bash
python -m pip install -r backend/requirements.txt
python -m backend.main
```

Default port: `8000`.

## Structure

- `app.py`: application factory, blueprint registration, shared error handlers.
- `routes/design.py`: frontend-facing endpoints used by `frontend/src/services/api.ts`.
- `routes/review.py`: Interactive Review contract placeholders.
- `routes/aut.py`: in-memory AUT endpoints for local API tests.
- `services/`: reusable business logic for parsing, risk, coverage, FSM, generation, oracle, optimization, export, and AUT storage.
- `data_loader.py`: shared requirement sample loader.

## Current Extension Points

- `services/parsing.py`: replace `parse_requirement` with the RAG/LLM parser while keeping the response schema stable.
- `services/generation.py`: replace deterministic case generation with EP/BVA/DT/FSM algorithm modules.
- `services/fsm.py`: plug in a real FSM builder when the algorithm module is ready.
- `routes/review.py`: add persistence, authentication, and real incremental regeneration.
- `services/exporting.py`: xlsx export uses `openpyxl` when available and falls back to CSV content otherwise.
