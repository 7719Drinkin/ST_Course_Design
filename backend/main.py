"""AutoTestDesign FastAPI 入口。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.utils.logging import configure_logging
from backend.routers import export, generation, health, retrieval

configure_logging()

app = FastAPI(
    title="AutoTestDesign Backend",
    version="0.4.0",
    description="基于 RAG 和 DeepSeek API 的软件测试知识生成后端。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(retrieval.router)
app.include_router(generation.router)
app.include_router(export.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
