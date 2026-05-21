"""导出服务。

负责 JSON / CSV / XLSX 内容构造，不依赖 FastAPI Request。
"""

from __future__ import annotations

import csv
import io
from typing import Any

from backend.models import ExportRequest


def _rows_from_request(request: ExportRequest) -> list[dict[str, Any]]:
    """把导出请求中的测试用例转换为表格行。"""
    return [case.model_dump() for case in request.test_cases]


def build_json_export(request: ExportRequest) -> dict[str, Any]:
    """构造 JSON 导出内容。"""
    return {
        "requirements": [item.model_dump() for item in request.requirements],
        "coverage_items": [item.model_dump() for item in request.coverage_items],
        "test_cases": [item.model_dump() for item in request.test_cases],
        "revisions": [item.model_dump() for item in request.revisions],
    }


def build_csv_export(request: ExportRequest) -> str:
    """构造 CSV 导出内容。"""
    rows = _rows_from_request(request)
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def build_xlsx_export(request: ExportRequest) -> io.BytesIO:
    """构造 XLSX 导出内容。

    缺少 openpyxl 时抛出运行时错误，由路由层转换成明确 HTTP 错误，
    避免把失败原因硬编码成一个“看似成功”的下载文件。
    """
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("XLSX 导出依赖 openpyxl 未安装") from exc

    rows = _rows_from_request(request)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "test_cases"
    if rows:
        headers = list(rows[0].keys())
        sheet.append(headers)
        for row in rows:
            sheet.append([str(row.get(header, "")) for header in headers])
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream
