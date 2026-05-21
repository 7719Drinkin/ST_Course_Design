"""导出接口。

当前支持 JSON / CSV / XLSX，导出逻辑放在 services.exporting 中。
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response, StreamingResponse

from backend.models import ExportRequest
from backend.services.exporting import build_csv_export, build_json_export, build_xlsx_export

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/json")
def export_json(request: ExportRequest) -> JSONResponse:
    """导出 JSON。"""
    return JSONResponse(content=build_json_export(request))


@router.post("/csv")
def export_csv(request: ExportRequest) -> Response:
    """导出 CSV。"""
    return Response(
        content=build_csv_export(request),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=autotestdesign.csv"},
    )


@router.post("/xlsx")
def export_xlsx(request: ExportRequest) -> StreamingResponse:
    """导出 XLSX。"""
    return StreamingResponse(
        build_xlsx_export(request),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=autotestdesign.xlsx"},
    )
