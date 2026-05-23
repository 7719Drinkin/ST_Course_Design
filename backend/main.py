"""AutoTestDesign FastAPI 入口。

本文件直接创建 FastAPI app，保持课程项目后端结构轻量、直观。
启动命令：
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import design, export, retrieval, review
from backend.utils.logging import configure_logging

configure_logging()

app = FastAPI(
    title="AutoTestDesign Backend",
    version="0.3.0",
    description="面向需求解析、风险分析、覆盖项生成、测试用例生成和人机审查的轻量后端。",
)

# 允许本地 Vite 前端访问；后续部署时可按需收紧来源。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册测试设计工具本身的路由；不注册 AUT 图书馆业务接口。
app.include_router(design.router)
app.include_router(review.router)
app.include_router(export.router)
app.include_router(retrieval.router)


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查接口，用于确认后端服务已启动。"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
