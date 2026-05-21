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
    """构造 XLSX 导出内容；缺少 openpyxl 时返回稳定占位内容。"""
    try:
        from openpyxl import Workbook
    except ImportError:
        # 课程项目联调时可能尚未安装依赖，保持接口稳定比直接报错更友好。
        return io.BytesIO("openpyxl 未安装，请执行 pip install -r backend/requirements.txt 后导出 XLSX。".encode("utf-8"))

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
