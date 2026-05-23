"""生成结果导出接口。"""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.export import ExportRequest, ExportResponse
from backend.services.export_service import export_markdown

router = APIRouter(tags=["export"])


@router.post("/export", response_model=ExportResponse)
def export_result(request: ExportRequest) -> ExportResponse:
    """把生成结果导出为指定格式。"""
    content = export_markdown(request.data)
    return ExportResponse(format=request.format, content=content)
