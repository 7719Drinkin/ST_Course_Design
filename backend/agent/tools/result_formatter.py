from __future__ import annotations

from typing import Any


DATA_KEYS = [
    "requirements",
    "analyzed_requirements",
    "coverage_goals",
    "coverage_items",
    "test_design_specs",
    "test_cases",
]


def format_success_result(raw_result: dict, rag_context: str | None = None) -> dict[str, Any]:
    """把 pipeline 成功结果整理成稳定的公开响应结构。"""

    data = _extract_data(raw_result)
    test_cases = data["test_cases"]
    coverage_items = data["coverage_items"]
    requirements = data["requirements"]

    return {
        "success": True,
        "data": data,
        "metadata": {
            "case_count": len(test_cases),
            "coverage_item_count": len(coverage_items),
            "requirement_count": len(requirements),
            "techniques": sorted(
                {
                    str(test_case.get("technique", ""))
                    for test_case in test_cases
                    if test_case.get("technique")
                }
            ),
            "has_rag_context": bool(rag_context),
        },
        "prompts_used": raw_result.get("prompts_used", []),
    }


def format_error_result(error: str, raw_result: dict | None = None) -> dict[str, Any]:
    """把任意失败结果整理成统一错误响应，尽量保留 partial_data。"""

    raw_result = raw_result or {}
    partial_result = raw_result.get("partial_result")
    partial_data = _extract_data(partial_result if isinstance(partial_result, dict) else raw_result)
    prompts_source = partial_result if isinstance(partial_result, dict) else raw_result

    return {
        "success": False,
        "error": error,
        "failed_step": raw_result.get("failed_step", ""),
        "partial_data": partial_data,
        "prompts_used": prompts_source.get("prompts_used", []),
    }


def _extract_data(raw_result: dict | None) -> dict[str, Any]:
    """按固定 data 字段提取结果，缺失字段统一补为空列表。"""

    raw_result = raw_result or {}
    return {key: raw_result.get(key, []) for key in DATA_KEYS}
