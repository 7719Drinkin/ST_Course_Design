"""基于 RAG 和 DeepSeek 的测试生成编排服务。"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from backend.rag_engine.prompt_builder import build_test_cases_prompt, build_test_points_prompt
from backend.schemas.generation import (
    GenerateTestCasesResponse,
    GenerateTestPointsResponse,
    SourceRef,
    TestPoint,
)
from backend.services.deepseek_service import chat_with_deepseek
from backend.services.retrieval_service import retrieve_chunks
from backend.utils.json_parser import parse_llm_json


class TestGenerationError(RuntimeError):
    """测试生成流程失败。"""


def _build_sources(retrieved_chunks: list[dict[str, Any]]) -> list[SourceRef]:
    """从 retrieval metadata 中提取去重后的 sources。"""
    sources: list[SourceRef] = []
    seen: set[tuple[str, str, str]] = set()

    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata") or {}
        source = str(metadata.get("source") or "")
        section = str(metadata.get("section") or metadata.get("chapter") or "")
        chunk_id = str(metadata.get("chunk_id") or "")
        key = (source, section, chunk_id)

        if not chunk_id or key in seen:
            continue

        seen.add(key)
        sources.append(SourceRef(source=source, section=section, chunk_id=chunk_id))

    return sources


def _validate_test_points_payload(
    payload: dict[str, Any],
    requirement: str,
    retrieved_chunks: list[dict[str, Any]],
) -> GenerateTestPointsResponse:
    """校验并补全测试点响应。"""
    payload.pop("sources", None)
    payload["requirement"] = requirement
    payload["sources"] = [source.model_dump() for source in _build_sources(retrieved_chunks)]

    if not retrieved_chunks:
        payload["context_quality"] = "low"

    try:
        response = GenerateTestPointsResponse.model_validate(payload)
    except ValidationError as exc:
        raise TestGenerationError(f"DeepSeek 返回的测试点 JSON 结构不符合约定：{exc}") from exc

    if not response.test_points:
        raise TestGenerationError("DeepSeek 没有生成任何测试点")

    return response


def _validate_test_cases_payload(
    payload: dict[str, Any],
    requirement: str,
    test_points: list[TestPoint],
    retrieved_chunks: list[dict[str, Any]],
) -> GenerateTestCasesResponse:
    """校验、补全并规范化测试用例响应。"""
    payload.pop("sources", None)
    payload["requirement"] = requirement
    payload["sources"] = [source.model_dump() for source in _build_sources(retrieved_chunks)]

    raw_cases = payload.get("test_cases")
    if not isinstance(raw_cases, list):
        raise TestGenerationError("DeepSeek 返回的测试用例 JSON 缺少 test_cases 数组")
    if not raw_cases:
        raise TestGenerationError("DeepSeek 没有生成任何测试用例")

    for index, test_case in enumerate(raw_cases, start=1):
        if isinstance(test_case, dict):
            test_case["case_id"] = f"TC{index:03d}"

    try:
        response = GenerateTestCasesResponse.model_validate(payload)
    except ValidationError as exc:
        raise TestGenerationError(f"DeepSeek 返回的测试用例 JSON 结构不符合约定：{exc}") from exc

    test_point_ids = {test_point.id for test_point in test_points}
    related_ids = {test_case.related_test_point for test_case in response.test_cases}

    unknown_ids = related_ids - test_point_ids
    if unknown_ids:
        raise TestGenerationError(f"测试用例 related_test_point 不存在：{sorted(unknown_ids)}")

    missing_ids = test_point_ids - related_ids
    if missing_ids:
        raise TestGenerationError(f"以下测试点没有生成测试用例：{sorted(missing_ids)}")

    return response


def _generate_test_points_with_context(
    requirement: str,
    top_k: int = 5,
) -> tuple[GenerateTestPointsResponse, list[dict[str, Any]]]:
    """生成测试点，并返回本次使用的 retrieval chunks。"""
    retrieved_chunks = retrieve_chunks(query=requirement, top_k=top_k, debug=True)
    messages = build_test_points_prompt(requirement=requirement, retrieved_chunks=retrieved_chunks)
    raw_text = chat_with_deepseek(messages, temperature=0.2)

    try:
        payload = parse_llm_json(raw_text)
    except ValueError as exc:
        raise TestGenerationError(f"DeepSeek 测试点生成结果 JSON 解析失败：{exc}") from exc

    return _validate_test_points_payload(payload, requirement, retrieved_chunks), retrieved_chunks


def generate_test_points(requirement: str, top_k: int = 5) -> GenerateTestPointsResponse:
    """生成结构化测试点。"""
    response, _ = _generate_test_points_with_context(requirement=requirement, top_k=top_k)
    return response


def generate_test_cases(requirement: str, top_k: int = 5) -> GenerateTestCasesResponse:
    """生成结构化测试用例。"""
    test_points_response, retrieved_chunks = _generate_test_points_with_context(requirement=requirement, top_k=top_k)
    test_points = [test_point.model_dump() for test_point in test_points_response.test_points]
    messages = build_test_cases_prompt(
        requirement=requirement,
        test_points=test_points,
        retrieved_chunks=retrieved_chunks,
    )
    raw_text = chat_with_deepseek(messages, temperature=0.2)

    try:
        payload = parse_llm_json(raw_text)
    except ValueError as exc:
        raise TestGenerationError(f"DeepSeek 测试用例生成结果 JSON 解析失败：{exc}") from exc

    return _validate_test_cases_payload(
        payload=payload,
        requirement=requirement,
        test_points=test_points_response.test_points,
        retrieved_chunks=retrieved_chunks,
    )
