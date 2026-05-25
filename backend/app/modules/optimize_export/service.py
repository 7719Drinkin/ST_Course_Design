from __future__ import annotations

from html import escape
from typing import Any
import io
import zipfile

from ..util import coverage_counts, csv_bytes, json_bytes, to_dicts
from ..store import workflow_store
from .schemas import (
    ExportBundle,
    ExportRequest,
    OptimizeRequest,
    OptimizeResponse,
    OptimizationResult,
)


class OptimizeExportService:
    def optimize(self, request: OptimizeRequest) -> OptimizeResponse:
        test_cases = to_dicts(request.test_cases) or workflow_store.get_list(request.session_id, "test_cases")
        coverage_items = to_dicts(request.coverage_items) or workflow_store.get_list(request.session_id, "coverage_items")
        risk_results = to_dicts(request.risk_results) or workflow_store.get_list(request.session_id, "risk_results")

        kept_ids = self._kept_tests(
            test_cases,
            coverage_items,
            risk_results,
            request.objective,
            request.preserve_high_risk_unique_coverage,
        )
        all_ids = [str(item.get("test_id")) for item in test_cases if item.get("test_id")]
        removed_ids = [item for item in all_ids if item not in kept_ids]
        preserved_coverage = sorted(
            {
                str(item.get("coverage_item_id"))
                for item in test_cases
                if item.get("test_id") in kept_ids and item.get("coverage_item_id")
            }
        )
        warnings = []
        expected_coverage = {str(item.get("coverage_item_id")) for item in coverage_items if item.get("coverage_item_id")}
        missing = sorted(expected_coverage - set(preserved_coverage))
        if missing:
            warnings.append("Coverage items without kept tests: " + ", ".join(missing))

        result = OptimizationResult(
            objective=request.objective,
            before_count=len(test_cases),
            after_count=len(kept_ids),
            kept_test_ids=kept_ids,
            removed_test_ids=removed_ids,
            coverage_preservation=[f"Preserved coverage item {item}" for item in preserved_coverage],
            warnings=warnings,
        )
        workflow_store.save_object(request.session_id, "optimization_result", result)
        return OptimizeResponse(session_id=request.session_id, optimization_result=result)

    def export_bundle(self, request: ExportRequest) -> ExportBundle:
        raw = workflow_store.export_bundle(request.session_id)
        if request.test_case_status == "approved_only":
            raw["test_cases"] = [
                item for item in raw.get("test_cases", []) if item.get("status") == "Approved"
            ]
        if not request.include_revisions:
            raw["revisions"] = []
        if not request.include_prompt_evidence:
            raw["prompt_evidence"] = []
        return ExportBundle(**raw)

    def export_bytes(self, request: ExportRequest) -> tuple[bytes, str, str]:
        bundle = self.export_bundle(request).model_dump(mode="json", by_alias=True)
        if request.format == "json":
            return json_bytes({"export_bundle": bundle}), "application/json", "aut_design_export.json"
        if request.format == "xlsx":
            return _xlsx_bytes(bundle), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "aut_design_export.xlsx"
        return csv_bytes(bundle), "text/csv; charset=utf-8", "aut_design_export.csv"

    def _kept_tests(
        self,
        test_cases: list[dict[str, Any]],
        coverage_items: list[dict[str, Any]],
        risk_results: list[dict[str, Any]],
        objective: str,
        preserve_high_risk_unique_coverage: bool,
    ) -> list[str]:
        if not test_cases:
            return []
        risk_by_id = {item.get("target_id"): item for item in risk_results}
        counts = coverage_counts(test_cases)
        kept: list[str] = []
        covered: set[str] = set()

        def priority(test_case: dict[str, Any]) -> tuple[int, str]:
            coverage_id = test_case.get("coverage_item_id")
            requirement_id = test_case.get("requirement_id")
            risk = risk_by_id.get(coverage_id) or risk_by_id.get(requirement_id) or {}
            level_score = {"High": 0, "Medium": 1, "Low": 2}.get(risk.get("risk_level"), 1)
            return level_score, str(test_case.get("test_id"))

        ordered = sorted(test_cases, key=priority) if objective == "risk_priority" else list(test_cases)
        if preserve_high_risk_unique_coverage:
            for item in ordered:
                coverage_id = str(item.get("coverage_item_id") or "")
                risk = risk_by_id.get(coverage_id) or risk_by_id.get(item.get("requirement_id")) or {}
                test_id = str(item.get("test_id") or "")
                if risk.get("risk_level") == "High" and counts.get(coverage_id) == 1 and test_id:
                    kept.append(test_id)
                    covered.add(coverage_id)

        for item in ordered:
            coverage_id = str(item.get("coverage_item_id") or "")
            test_id = str(item.get("test_id") or "")
            if not test_id:
                continue
            if coverage_id and coverage_id not in covered:
                kept.append(test_id)
                covered.add(coverage_id)
            elif not coverage_id and test_id not in kept:
                kept.append(test_id)

        expected_coverage = {str(item.get("coverage_item_id")) for item in coverage_items if item.get("coverage_item_id")}
        if expected_coverage and expected_coverage.issubset(covered):
            return _dedupe(kept)
        return _dedupe(kept)


def _dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _xlsx_bytes(bundle: dict[str, Any]) -> bytes:
    sheets = {
        "requirements": bundle.get("requirements", []),
        "risk_results": bundle.get("risk_results", []),
        "coverage_items": bundle.get("coverage_items", []),
        "strategies": bundle.get("strategies", []),
        "test_cases": bundle.get("test_cases", []),
        "revisions": bundle.get("revisions", []),
        "analysis_results": bundle.get("analysis_results", []),
        "prompt_evidence": bundle.get("prompt_evidence", []),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml(list(sheets)))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(sheets)))
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, (name, rows) in enumerate(sheets.items(), start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(name, rows))
    return output.getvalue()


def _content_types_xml(sheet_count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides}</Types>"
    )


def _root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name[:31])}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def _workbook_rels_xml(sheet_count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    rels += (
        f'<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rels}</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        "</styleSheet>"
    )


def _sheet_xml(name: str, rows: list[dict[str, Any]]) -> str:
    columns = _columns(rows)
    sheet_rows = [_row_xml(1, columns)]
    for index, item in enumerate(rows, start=2):
        sheet_rows.append(_row_xml(index, [_cell_value(item.get(column)) for column in columns]))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns or ["empty"]


def _row_xml(index: int, values: list[Any]) -> str:
    cells = "".join(
        f'<c r="{_column_name(offset)}{index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
        for offset, value in enumerate(values, start=1)
    )
    return f'<row r="{index}">{cells}</row>'


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _cell_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return str(value)
    if value is None:
        return ""
    return str(value)
