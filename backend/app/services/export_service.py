"""Export service for JSON, CSV, and XLSX downloads."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from backend.app.schemas.export import ExportRequest


class ExportService:
    def build_json(self, request: ExportRequest) -> dict[str, Any]:
        return {
            "test_cases": request.test_cases,
            "risk_scores": request.risk_scores,
            "coverage_items": request.coverage_items,
            "revisions": request.revisions,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    def build_csv(self, request: ExportRequest) -> str:
        rows = request.test_cases
        if not rows:
            return ""
        output = io.StringIO()
        headers = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell_value(row.get(key)) for key in headers})
        return output.getvalue()

    def build_xlsx(self, request: ExportRequest) -> io.BytesIO:
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "test_cases"
        rows = request.test_cases
        if rows:
            headers = list(rows[0].keys())
            sheet.append(headers)
            for row in rows:
                sheet.append([_cell_value(row.get(header)) for header in headers])
        stream = io.BytesIO()
        workbook.save(stream)
        stream.seek(0)
        return stream

    def empty_request(self, export_format: str) -> ExportRequest:
        return ExportRequest(format=export_format)


def _cell_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return str(value)
    return "" if value is None else str(value)


export_service = ExportService()
