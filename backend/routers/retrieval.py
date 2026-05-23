"""RAG 检索调试 API。"""

from __future__ import annotations

from fastapi import APIRouter

from backend.models import RetrieveRequest, RetrieveResponse
from backend.services.retrieval import retrieve_chunks

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    """根据 query 返回结构化检索结果。"""
    results = retrieve_chunks(
        query=request.query,
        top_k=request.top_k,
        where=request.where,
        debug=True,
    )
    return RetrieveResponse(query=request.query, results=results)
