"""Interactive review placeholder routes.

These routes preserve the Day7+ data contract. Persistence, auth, and
incremental regeneration are intentionally left as extension points.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request

review_bp = Blueprint("review", __name__, url_prefix="/review")

_sessions: dict[str, dict] = {}
_revisions: list[dict] = []


def _body() -> dict:
    data = request.get_json(silent=False)
    if not isinstance(data, dict):
        abort(400, "JSON object body is required")
    return data


@review_bp.post("/sessions")
def create_session():
    body = _body()
    session_id = body.get("session_id", "DS-AUT-001")
    session = {
        "session_id": session_id,
        "requirement_ids": body.get("requirement_ids", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": body.get("status", "draft"),
    }
    _sessions[session_id] = session
    return jsonify(session), 201


@review_bp.post("/revisions")
def create_revision():
    body = _body()
    revision = {
        "revision_id": body.get("revision_id", f"REV-{len(_revisions) + 1:04d}"),
        "session_id": body.get("session_id", "DS-AUT-001"),
        "target_type": body.get("target_type", ""),
        "target_id": body.get("target_id", ""),
        "operation": body.get("operation", "update"),
        "before": body.get("before", {}),
        "after": body.get("after", {}),
        "reason": body.get("reason", ""),
        "created_by": body.get("created_by", "tester"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _revisions.append(revision)
    return jsonify(revision), 201


@review_bp.post("/regenerate")
def regenerate():
    body = _body()
    return jsonify(
        {
            "session_id": body.get("session_id", "DS-AUT-001"),
            "revision_id": body.get("revision_id", ""),
            "affected_coverage_item_ids": body.get("affected_coverage_item_ids", []),
            "mode": body.get("mode", "incremental"),
            "status": "pending_agent_implementation",
            "generated_test_cases": [],
        }
    )
