"""Step 6 routes: optimization and export."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from .schemas import ExportRequest, ExportResponse, OptimizeRequest, OptimizeResponse
from .service import OptimizeExportService

router = APIRouter(tags=["06 optimize-export"])


def get_optimize_export_service() -> OptimizeExportService:
    return OptimizeExportService()


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize(
    req: OptimizeRequest,
    svc: OptimizeExportService = Depends(get_optimize_export_service),
) -> OptimizeResponse:
    return svc.optimize(req)


@router.get("/export")
async def export_get(
    session_id: str = Query(...),
    format: Literal["json", "csv", "xlsx"] = Query(...),
    svc: OptimizeExportService = Depends(get_optimize_export_service),
):
    req = ExportRequest(session_id=session_id, format=format)
    return _export_response(req, svc)


@router.post("/export", response_model=None)
async def export_post(
    req: ExportRequest,
    svc: OptimizeExportService = Depends(get_optimize_export_service),
):
    return _export_response(req, svc)


def _export_response(req: ExportRequest, svc: OptimizeExportService):
    if req.format == "json":
        return ExportResponse(file=None, export_bundle=svc.export_bundle(req))
    raw, media_type, filename = svc.export_bytes(req)
    return Response(
        content=raw,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
