"""
AutoTestDesign reference backend (C-provided baseline for A/B/E to extend).

Run: uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from backend.data_loader import get_by_id, load_requirements

app = FastAPI(title="AutoTestDesign API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────


class IngestRequest(BaseModel):
    source_type: Literal["text", "json", "csv"] = "text"
    content: str = ""


class IngestResponse(BaseModel):
    requirements: list[dict[str, str]]
    errors: list[str] = Field(default_factory=list)


class ParseRequest(BaseModel):
    requirement_id: str
    raw_requirement: str = ""


class ParseResponse(BaseModel):
    requirement_id: str
    input_fields: list[str]
    data_ranges: list[str]
    conditions: list[str]
    expected_action: str
    confidence: float
    missing_fields: list[str]


class FsmRequest(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)


class RiskRequest(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)
    coverage_items: list[dict[str, Any]] = Field(default_factory=list)


class OracleRequest(BaseModel):
    test_ids: list[str] = Field(default_factory=list)


class OptimizeRequest(BaseModel):
    mode: Literal["risk_priority", "normal"] = "risk_priority"
    test_ids: list[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    format: Literal["json", "csv", "xlsx"] = "json"
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    revisions: list[dict[str, Any]] = Field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _priority_to_risk(priority: str) -> tuple[int, int, str]:
    mapping = {
        "High": (5, 5, "High"),
        "Medium": (3, 3, "Medium"),
        "Low": (2, 2, "Low"),
    }
    impact, likelihood, level = mapping.get(priority, (3, 3, "Medium"))
    return impact, likelihood, level


def _build_test_cases(requirement_ids: list[str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    reqs = load_requirements()
    if requirement_ids:
        reqs = [r for r in reqs if r["id"] in requirement_ids]

    for req in reqs:
        rid = req["id"]
        priority = req.get("priority", "Medium")
        techniques = req.get("techniques", ["EP"])
        for i, tech in enumerate(techniques[:3]):
            cases.append(
                {
                    "test_id": f"TC-{rid.replace('REQ-', '')}-{i + 1:03d}",
                    "requirement_id": rid,
                    "technique": tech,
                    "title": f"{req['title']} ({tech})",
                    "preconditions": req.get("conditions", []),
                    "input_data": {f: f"sample_{f}" for f in req.get("input_fields", [])[:2]},
                    "test_steps": [f"Execute scenario for {rid} using {tech}"],
                    "expected_result": req.get("expected_action", ""),
                    "risk_level": priority,
                    "standard_ref": f"ISO/IEC/IEEE 29119-4 ({tech})",
                    "status": "Draft",
                    "coverage_item_id": f"CI-{rid}",
                }
            )
    return cases


def _oracle_for(test_id: str) -> dict[str, Any]:
    needs_review = test_id.endswith("002")
    return {
        "test_id": test_id,
        "llm_verdict": "Pass" if not needs_review else "Pass",
        "rule_verdict": "Pass" if not needs_review else "Fail",
        "confidence": 0.95 if not needs_review else 0.56,
        "needs_review": needs_review,
    }


# ── Routes ──────────────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest(body: IngestRequest) -> IngestResponse:
    reqs = load_requirements()
    if body.content.strip():
        # Single pasted requirement
        requirements = [
            {
                "requirement_id": "REQ-AUT-PASTE-001",
                "raw_requirement": body.content.strip(),
                "source": "direct_input",
            }
        ]
    else:
        requirements = [
            {
                "requirement_id": r["id"],
                "raw_requirement": r["raw_requirement"],
                "source": "aut_15_requirements",
            }
            for r in reqs
        ]
    return IngestResponse(requirements=requirements, errors=[])


@app.post("/parse", response_model=ParseResponse)
def parse(body: ParseRequest) -> ParseResponse:
    req = get_by_id(body.requirement_id)
    if req:
        missing = []
        if not req.get("data_ranges"):
            missing.append("data_ranges")
        return ParseResponse(
            requirement_id=req["id"],
            input_fields=req.get("input_fields", []),
            data_ranges=req.get("data_ranges", []),
            conditions=req.get("conditions", []),
            expected_action=req.get("expected_action", ""),
            confidence=0.88 if not missing else 0.72,
            missing_fields=missing,
        )
    return ParseResponse(
        requirement_id=body.requirement_id,
        input_fields=[],
        data_ranges=[],
        conditions=[],
        expected_action="",
        confidence=0.5,
        missing_fields=["input_fields", "conditions", "expected_action"],
    )


@app.post("/risk")
def risk(body: RiskRequest) -> list[dict[str, Any]]:
    reqs = load_requirements()
    if body.requirement_ids:
        reqs = [r for r in reqs if r["id"] in body.requirement_ids]
    result = []
    for r in reqs:
        impact, likelihood, level = _priority_to_risk(r.get("priority", "Medium"))
        result.append(
            {
                "requirement_id": r["id"],
                "impact": impact,
                "likelihood": likelihood,
                "score": impact * likelihood,
                "level": level,
            }
        )
    return result


@app.post("/coverage")
def coverage(body: RiskRequest) -> list[dict[str, Any]]:
    """Coverage items derived from requirements (B/A can replace with RAG logic)."""
    reqs = load_requirements()
    if body.requirement_ids:
        reqs = [r for r in reqs if r["id"] in body.requirement_ids]
    return [
        {
            "coverage_item_id": f"CI-{r['id']}",
            "requirement_id": r["id"],
            "description": f"Cover: {r['title']}",
            "techniques": r.get("techniques", ["EP"]),
            "strategy_rationale": f"Selected {', '.join(r.get('techniques', ['EP']))} per requirement techniques field.",
        }
        for r in reqs
    ]


@app.post("/fsm")
def fsm(body: FsmRequest) -> dict[str, Any]:
    return {
        "states": ["Available", "Borrowed", "Returned", "Rejected"],
        "transitions": [
            {
                "from": "Available",
                "to": "Borrowed",
                "event": "POST /api/borrow",
                "condition": "book exists, member exists, availableCopies > 0",
            },
            {
                "from": "Borrowed",
                "to": "Returned",
                "event": "POST /api/return",
                "condition": "borrowing record exists",
            },
            {
                "from": "Available",
                "to": "Rejected",
                "event": "POST /api/borrow",
                "condition": "availableCopies == 0",
            },
        ],
        "coverage": {
            "all_states": ["Available", "Borrowed", "Returned", "Rejected"],
            "all_transitions": [
                "Available->Borrowed",
                "Borrowed->Returned",
                "Available->Rejected",
            ],
        },
        "mermaid": (
            "stateDiagram-v2\n"
            "    [*] --> Available\n"
            "    Available --> Borrowed : POST /api/borrow [copies > 0]\n"
            "    Available --> Rejected : POST /api/borrow [copies == 0]\n"
            "    Borrowed --> Returned : POST /api/return"
        ),
    }


@app.post("/generate")
def generate(body: GenerateRequest) -> list[dict[str, Any]]:
    return _build_test_cases(body.requirement_ids)


@app.post("/oracle")
def oracle(body: OracleRequest) -> list[dict[str, Any]]:
    ids = body.test_ids or [tc["test_id"] for tc in _build_test_cases([])]
    return [_oracle_for(tid) for tid in ids]


@app.post("/optimize")
def optimize(body: OptimizeRequest) -> dict[str, Any]:
    all_cases = _build_test_cases([])
    before = len(body.test_ids) if body.test_ids else len(all_cases)
    after = max(1, before // 2) if body.mode == "risk_priority" else max(1, before - 1)
    removed = [tc["test_id"] for tc in all_cases[after:]]
    return {
        "before_count": before,
        "after_count": after,
        "mode": body.mode,
        "reduction_rate": round((1 - after / before) * 100) if before else 0,
        "removed_test_ids": removed,
    }


def _build_export_response(body: ExportRequest) -> Response:
    payload = {
        "test_cases": body.test_cases,
        "revisions": body.revisions,
        "exported_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    if body.format == "json":
        return JSONResponse(content=payload)
    buf = io.StringIO()
    if body.test_cases:
        writer = csv.DictWriter(buf, fieldnames=list(body.test_cases[0].keys()))
        writer.writeheader()
        for row in body.test_cases:
            flat = {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()}
            writer.writerow(flat)
    media = "text/csv" if body.format in ("csv", "xlsx") else "text/csv"
    return Response(content=buf.getvalue(), media_type=media)


@app.post("/export")
def export_post(body: ExportRequest) -> Response:
    return _build_export_response(body)


@app.get("/export/{fmt}")
def export_get(fmt: Literal["json", "csv", "xlsx"]) -> Response:
    cases = _build_test_cases([])
    return _build_export_response(ExportRequest(format=fmt, test_cases=cases, revisions=[]))
