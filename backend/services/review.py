"""Interactive Review 修改记录服务。

第一版用内存列表保存修改记录，保持简单，可直接被 pytest 调用。
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.models import RegenerateRequest, ReviseRequest, RevisionRecord

_REVISION_HISTORY: list[RevisionRecord] = []


def revise_item(request: ReviseRequest) -> RevisionRecord:
    """保存一次人工修改记录。"""
    record = RevisionRecord(
        revision_id=f"REV-{len(_REVISION_HISTORY) + 1:04d}",
        item_id=request.item_id,
        item_type=request.item_type,
        field_changed=request.field_changed,
        original_value=request.original_value,
        revised_value=request.revised_value,
        revision_reason=request.revision_reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    _REVISION_HISTORY.append(record)
    return record


def get_history() -> list[RevisionRecord]:
    """返回当前进程内的修改历史。"""
    return list(_REVISION_HISTORY)


def regenerate_from_revision(request: RegenerateRequest) -> dict[str, object]:
    """根据修改记录触发再生成；当前返回稳定占位结构。"""
    return {
        "revision_id": request.revision_id,
        "item_id": request.item_id,
        "mode": request.mode,
        "status": "stub_pending_generation",
        "generated_test_cases": [],
    }
