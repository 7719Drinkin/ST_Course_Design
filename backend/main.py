"""Entrypoint for local Flask backend.

Run:
    python -m backend.main
or:
    flask --app backend.main run --port 8000
"""

from __future__ import annotations

from backend.app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
