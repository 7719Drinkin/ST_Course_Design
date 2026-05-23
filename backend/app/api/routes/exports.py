"""Export routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse

from backend.app.schemas.export import ExportRequest
from backend.app.services.export_service import export_service

router = APIRouter(tags=["export"])


@router.post("/export")
def export(request: ExportRequest) -> JSONResponse | Response | StreamingResponse:
    return _export_response(request)


@router.get("/export/{export_format}")
def export_empty(export_format: str) -> JSONResponse | Response | StreamingResponse:
    if export_format not in {"json", "csv", "xlsx"}:
        raise HTTPException(status_code=400, detail="Unsupported export format")
    request = export_service.empty_request(export_format)
    return _export_response(request)


def _export_response(request: ExportRequest) -> JSONResponse | Response | StreamingResponse:
    if request.format == "json":
        return JSONResponse(content=export_service.build_json(request))
    if request.format == "csv":
        return Response(
            content=export_service.build_csv(request),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=autotest_export.csv"},
        )
    if request.format == "xlsx":
        return StreamingResponse(
            export_service.build_xlsx(request),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=autotest_export.xlsx"},
        )
    raise HTTPException(status_code=400, detail="Unsupported export format")
