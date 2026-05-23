"""交互式评审接口。

用于记录人工修改、查看历史，并为后续增量再生成预留稳定入口。
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.models import RegenerateRequest, ReviseRequest, RevisionRecord
from backend.services.review import get_history, regenerate_from_revision, revise_item

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/history", response_model=list[RevisionRecord])
def history() -> list[RevisionRecord]:
    """返回人工修改历史。"""
    return get_history()


@router.post("/revise", response_model=RevisionRecord)
def revise(request: ReviseRequest) -> RevisionRecord:
    """保存一次人工修改。"""
    return revise_item(request)


@router.post("/regenerate")
def regenerate(request: RegenerateRequest) -> dict[str, object]:
    """根据修改记录触发再生成；当前为稳定占位实现。"""
    return regenerate_from_revision(request)
