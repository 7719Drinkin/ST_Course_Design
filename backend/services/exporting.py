"""Artifact export helpers."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from flask import Response, jsonify, send_file


def build_export_payload(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "test_cases": body.get("test_cases", []),
        "risk_scores": body.get("risk_scores", []),
        "coverage_items": body.get("coverage_items", []),
        "revisions": body.get("revisions", []),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def export_response(format_: str, payload: dict[str, Any]):
    if format_ == "json":
        return jsonify(payload)

    if format_ == "xlsx":
        xlsx = _build_xlsx(payload.get("test_cases", []))
        if xlsx is not None:
            return send_file(
                xlsx,
                as_attachment=True,
                download_name="autotestdesign_export.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    csv_text = _build_csv(payload.get("test_cases", []))
    mimetype = "text/csv; charset=utf-8"
    return Response(csv_text, mimetype=mimetype, headers={"Content-Disposition": "attachment; filename=autotestdesign_export.csv"})


def _build_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    if not rows:
        return ""
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    return output.getvalue()


def _build_xlsx(rows: list[dict[str, Any]]) -> io.BytesIO | None:
    try:
        from openpyxl import Workbook
    except ImportError:
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "test_cases"
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([json.dumps(row.get(h), ensure_ascii=False) if isinstance(row.get(h), (list, dict)) else row.get(h) for h in headers])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
