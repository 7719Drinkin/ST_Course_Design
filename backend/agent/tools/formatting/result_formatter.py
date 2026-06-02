from __future__ import annotations

from typing import Any


DATA_KEYS = [
    "requirements",
    "analyzed_requirements",
    "risk_analysis",
    "coverage_goals",
    "coverage_items",
    "test_design_specs",
    "test_cases",
    "fsm",
    "fsm_test_cases",
    "all_test_cases",
    "oracle_results",
]


def format_success_result(raw_result: dict, rag_context: str | None = None) -> dict[str, Any]:
    """把 pipeline 成功结果整理成稳定的公开响应结构。"""

    data = _extract_data(raw_result)
    test_cases = data["test_cases"]
    all_test_cases = data["all_test_cases"]
    coverage_items = data["coverage_items"]
    requirements = data["requirements"]

    return {
        "success": True,
        "data": data,
        "metadata": {
            "case_count": len(all_test_cases) if isinstance(all_test_cases, list) else len(test_cases),
            "coverage_item_count": len(coverage_items),
            "requirement_count": len(requirements),
            "techniques": sorted(
                {
                    str(test_case.get("technique", ""))
                    for test_case in (
                        all_test_cases
                        if isinstance(all_test_cases, list) and all_test_cases
                        else test_cases
                    )
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
    return {
        "requirements": raw_result.get("requirements", []),
        "analyzed_requirements": raw_result.get("analyzed_requirements", []),
        "risk_analysis": raw_result.get("risk_analysis", []),
        "coverage_goals": raw_result.get("coverage_goals", []),
        "coverage_items": raw_result.get("coverage_items", []),
        "test_design_specs": raw_result.get("test_design_specs", []),
        "test_cases": raw_result.get("test_cases", []),
        "fsm": raw_result.get("fsm"),
        "fsm_test_cases": raw_result.get("fsm_test_cases", []),
        "all_test_cases": raw_result.get("all_test_cases", []),
        "oracle_results": raw_result.get("oracle_results", []),
    }
