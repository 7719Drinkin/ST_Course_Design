"""健康检查接口。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """返回服务健康状态。"""
    return {"status": "ok"}
