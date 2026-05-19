"""Frontend-facing AutoTestDesign API routes."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, request

from backend.data_loader import load_requirements
from backend.services.exporting import build_export_payload, export_response
from backend.services.fsm import build_fsm
from backend.services.generation import build_oracle_results, build_test_cases, optimize_suite
from backend.services.parsing import ingest_requirements, parse_requirement
from backend.services.risk import build_coverage_items, build_risk_entries

design_bp = Blueprint("design", __name__)


def _json_body() -> dict:
    data = request.get_json(silent=False)
    if not isinstance(data, dict):
        abort(400, "JSON object body is required")
    return data


@design_bp.post("/ingest")
def ingest():
    body = _json_body()
    return jsonify(ingest_requirements(body.get("source_type", "text"), body.get("content", "")))


@design_bp.post("/parse")
def parse():
    body = _json_body()
    requirement_id = body.get("requirement_id")
    if not requirement_id:
        abort(400, "requirement_id is required")
    return jsonify(parse_requirement(requirement_id, body.get("raw_requirement", "")))


@design_bp.post("/risk")
def risk():
    body = _json_body()
    return jsonify(build_risk_entries(body.get("requirement_ids", [])))


@design_bp.post("/coverage")
def coverage():
    body = _json_body()
    return jsonify(build_coverage_items(body.get("requirement_ids", [])))


@design_bp.get("/dashboard")
def dashboard():
    reqs = load_requirements()
    cases = build_test_cases()
    high_risk_count = sum(1 for req in reqs if req.get("priority") == "High")
    return jsonify(
        {
            "summary": {
                "total_requirements": len(reqs),
                "generated_tests": len(cases),
                "high_risk_count": high_risk_count,
                "ci_status": "passing",
            },
            "ragas": {"enabled": False, "answer_relevancy": None, "faithfulness": None},
        }
    )


@design_bp.post("/fsm")
def fsm():
    body = _json_body()
    return jsonify(build_fsm(body.get("requirement_ids", [])))


@design_bp.post("/generate")
def generate():
    body = _json_body()
    return jsonify(build_test_cases(body.get("requirement_ids", [])))


@design_bp.post("/oracle")
def oracle():
    body = _json_body()
    return jsonify(build_oracle_results(body.get("test_ids", [])))


@design_bp.post("/optimize")
def optimize():
    body = _json_body()
    return jsonify(optimize_suite(body.get("mode", "risk_priority"), body.get("test_ids", [])))


@design_bp.post("/export")
def export_post():
    body = _json_body()
    format_ = body.get("format", "json")
    if format_ not in {"json", "csv", "xlsx"}:
        abort(400, "format must be json, csv, or xlsx")
    return export_response(format_, build_export_payload(body))


@design_bp.get("/export/<format_>")
def export_get(format_: str):
    if format_ not in {"json", "csv", "xlsx"}:
        abort(404)
    payload = build_export_payload({"test_cases": build_test_cases(), "revisions": []})
    return export_response(format_, payload)
