from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any
import io
import zipfile

from ..util import csv_bytes, json_bytes, to_dicts
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
        if request.test_cases:
            workflow_store.save_many(request.session_id, "test_cases", request.test_cases, "test_id")
        if request.coverage_items:
            workflow_store.save_many(request.session_id, "coverage_items", request.coverage_items, "coverage_item_id")
        if request.risk_results:
            workflow_store.save_many(request.session_id, "risk_results", request.risk_results, "target_id")

        optimization_coverage_items = _coverage_with_fsm_items(coverage_items, test_cases)
        kept_ids = self._kept_tests(
            test_cases,
            optimization_coverage_items,
            risk_results,
            request.objective,
            request.preserve_high_risk_unique_coverage,
        )
        all_ids = [str(item.get("test_id")) for item in test_cases if item.get("test_id")]
        removed_ids = [item for item in all_ids if item not in kept_ids]
        preserved_coverage = sorted(_covered_ids([item for item in test_cases if item.get("test_id") in kept_ids]))
        warnings = []
        expected_coverage = {
            str(item.get("coverage_item_id"))
            for item in optimization_coverage_items
            if item.get("coverage_item_id")
        }
        missing = sorted(expected_coverage - set(preserved_coverage))
        if missing:
            warnings.append("Coverage items without kept tests: " + ", ".join(missing))
        rejected_only = sorted(
            coverage_id
            for coverage_id in expected_coverage
            if _tests_for_coverage(test_cases, coverage_id)
            and all(item.get("status") == "Rejected" for item in _tests_for_coverage(test_cases, coverage_id))
        )
        if rejected_only:
            warnings.append("Coverage items only covered by rejected tests; add replacement tests: " + ", ".join(rejected_only))
        tests_without_coverage = sorted(
            str(item.get("test_id"))
            for item in test_cases
            if item.get("test_id") and not _coverage_ids(item)
        )
        if tests_without_coverage:
            warnings.append("Tests without coverage mapping: " + ", ".join(tests_without_coverage))
        rejected_kept = sorted(
            str(item.get("test_id"))
            for item in test_cases
            if item.get("test_id") in kept_ids and item.get("status") == "Rejected"
        )
        if rejected_kept:
            warnings.append("Rejected tests kept because they preserve unique coverage: " + ", ".join(rejected_kept))

        result = OptimizationResult(
            objective=request.objective,
            before_count=len(test_cases),
            after_count=len(kept_ids),
            kept_test_ids=kept_ids,
            removed_test_ids=removed_ids,
            coverage_preservation=[
                f"Preserved {len(preserved_coverage)}/{len(expected_coverage or preserved_coverage)} coverage items.",
                *[f"Preserved coverage item {item}" for item in preserved_coverage],
            ],
            warnings=warnings,
        )
        workflow_store.save_object(request.session_id, "optimization_result", result)
        return OptimizeResponse(session_id=request.session_id, optimization_result=result)

    def export_bundle(self, request: ExportRequest) -> ExportBundle:
        raw = workflow_store.export_bundle(request.session_id)
        snapshot_fields = {
            "requirements": request.requirements,
            "risk_results": request.risk_results,
            "coverage_items": request.coverage_items,
            "strategies": request.strategies,
            "test_cases": request.test_cases,
            "oracle_results": request.oracle_results,
            "revisions": request.revisions,
            "prompt_evidence": request.prompt_evidence,
            "analysis_results": request.analysis_results,
        }
        for key, value in snapshot_fields.items():
            if value is not None:
                raw[key] = to_dicts(value)
                workflow_store.save_many(request.session_id, key, value, _export_id_field(key), replace_all=True)
        if request.optimization_result is not None:
            raw["optimization_result"] = request.optimization_result.model_dump(mode="json")
            workflow_store.save_object(request.session_id, "optimization_result", request.optimization_result)
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
        risk_by_id = _risk_by_id(risk_results)
        expected_coverage = {
            str(item.get("coverage_item_id"))
            for item in coverage_items
            if item.get("coverage_item_id")
        } or _covered_ids(test_cases)
        counts = _coverage_counts(test_cases)
        kept: list[str] = []
        covered: set[str] = set()

        def priority(test_case: dict[str, Any]) -> tuple[int, int, int, str]:
            risk = _risk_for_test(test_case, risk_by_id)
            level_score = {"High": 0, "Medium": 1, "Low": 2}.get(risk.get("risk_level"), 1)
            priority_score = {"P1": 0, "P2": 1, "P3": 2}.get(
                risk.get("test_priority") or test_case.get("priority"),
                1,
            )
            status_score = {"Approved": 0, "Draft": 1, "Rejected": 2}.get(test_case.get("status"), 1)
            return level_score, priority_score, status_score, str(test_case.get("test_id"))

        eligible_tests = [item for item in test_cases if item.get("status") != "Rejected"]
        ordered = sorted(eligible_tests, key=priority) if objective == "risk_priority" else list(eligible_tests)
        if preserve_high_risk_unique_coverage:
            for item in ordered:
                coverage_ids = _coverage_ids(item)
                risk = _risk_for_test(item, risk_by_id)
                test_id = str(item.get("test_id") or "")
                if (
                    risk.get("risk_level") == "High"
                    and coverage_ids
                    and any(counts.get(coverage_id) == 1 for coverage_id in coverage_ids)
                    and test_id
                ):
                    kept.append(test_id)
                    covered.update(coverage_ids)

        remaining = [item for item in ordered if str(item.get("test_id") or "") not in kept]
        while expected_coverage - covered:
            candidate = _best_candidate(remaining, covered, risk_by_id, objective)
            if candidate is None:
                break
            test_id = str(candidate.get("test_id") or "")
            kept.append(test_id)
            covered.update(_coverage_ids(candidate))
            remaining = [item for item in remaining if str(item.get("test_id") or "") != test_id]

        for item in remaining:
            test_id = str(item.get("test_id") or "")
            if test_id and not _coverage_ids(item):
                kept.append(test_id)
        return _dedupe(kept)


def _dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _coverage_with_fsm_items(
    coverage_items: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_ids = {
        str(item.get("coverage_item_id") or "")
        for item in coverage_items
        if item.get("coverage_item_id")
    }
    augmented = list(coverage_items)
    for test_case in test_cases:
        if str(test_case.get("technique") or "").upper() != "FSM":
            continue
        for coverage_id in _coverage_ids(test_case):
            if coverage_id in existing_ids:
                continue
            existing_ids.add(coverage_id)
            augmented.append(
                {
                    "coverage_item_id": coverage_id,
                    "requirement_id": str(test_case.get("requirement_id") or ""),
                    "technique": "FSM",
                    "description": str(test_case.get("title") or "FSM coverage inferred from test case."),
                }
            )
    return augmented


def _coverage_ids(test_case: dict[str, Any]) -> set[str]:
    raw = (
        test_case.get("coverage_item_ids")
        or test_case.get("coverage_items")
        or test_case.get("covered_coverage_item_ids")
    )
    if isinstance(raw, list):
        return {str(item) for item in raw if str(item).strip()}
    coverage_id = test_case.get("coverage_item_id")
    return {str(coverage_id)} if coverage_id else set()


def _covered_ids(test_cases: list[dict[str, Any]]) -> set[str]:
    covered: set[str] = set()
    for test_case in test_cases:
        covered.update(_coverage_ids(test_case))
    return covered


def _tests_for_coverage(test_cases: list[dict[str, Any]], coverage_id: str) -> list[dict[str, Any]]:
    return [item for item in test_cases if coverage_id in _coverage_ids(item)]


def _coverage_counts(test_cases: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for test_case in test_cases:
        counts.update(_coverage_ids(test_case))
    return counts


def _risk_by_id(risk_results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in risk_results:
        for key in ("target_id", "requirement_id", "coverage_item_id"):
            value = item.get(key)
            if value:
                result[str(value)] = item
    return result


def _risk_for_test(test_case: dict[str, Any], risk_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for coverage_id in _coverage_ids(test_case):
        if coverage_id in risk_by_id:
            return risk_by_id[coverage_id]
    requirement_id = str(test_case.get("requirement_id") or "")
    return risk_by_id.get(requirement_id, {})


def _best_candidate(
    test_cases: list[dict[str, Any]],
    covered: set[str],
    risk_by_id: dict[str, dict[str, Any]],
    objective: str,
) -> dict[str, Any] | None:
    candidates = [item for item in test_cases if _coverage_ids(item) - covered]
    if not candidates:
        return None

    def score(test_case: dict[str, Any]) -> tuple[int, float, int, int, str]:
        uncovered_gain = len(_coverage_ids(test_case) - covered)
        risk = _risk_for_test(test_case, risk_by_id)
        risk_score = float(risk.get("risk_score") or 0)
        status_score = {"Approved": 2, "Draft": 1, "Rejected": 0}.get(test_case.get("status"), 1)
        priority_score = {"P1": 3, "P2": 2, "P3": 1}.get(
            risk.get("test_priority") or test_case.get("priority"),
            2,
        )
        if objective == "risk_priority":
            return risk_score, uncovered_gain, status_score, priority_score, str(test_case.get("test_id") or "")
        return uncovered_gain, risk_score, status_score, priority_score, str(test_case.get("test_id") or "")

    return max(candidates, key=score)


def _xlsx_bytes(bundle: dict[str, Any]) -> bytes:
    sheets = {
        "requirements": bundle.get("requirements", []),
        "risk_results": bundle.get("risk_results", []),
        "coverage_items": bundle.get("coverage_items", []),
        "strategies": bundle.get("strategies", []),
        "test_cases": bundle.get("test_cases", []),
        "oracle_results": bundle.get("oracle_results", []),
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


def _export_id_field(key: str) -> str | None:
    return {
        "requirements": "requirement_id",
        "risk_results": "target_id",
        "coverage_items": "coverage_item_id",
        "strategies": "strategy_id",
        "test_cases": "test_id",
        "oracle_results": "test_id",
        "revisions": "revision_id",
        "prompt_evidence": "evidence_id",
        "analysis_results": None,
    }.get(key)
