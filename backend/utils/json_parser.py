"""LLM JSON 清洗与解析工具。"""

from __future__ import annotations

import json
import re

from backend.utils.logging import get_logger

logger = get_logger("json_parser")


def _strip_code_fence(text: str) -> str:
    """清理 ```json 代码块包裹。"""
    cleaned = text.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return fence_match.group(1).strip() if fence_match else cleaned


def _extract_first_json_object(text: str) -> str:
    """从混杂文本中提取第一个 JSON object。"""
    start = text.find("{")
    if start < 0:
        raise ValueError("DeepSeek 返回内容中没有找到 JSON object")

    in_string = False
    escaped = False
    depth = 0

    for index in range(start, len(text)):
        char = text[index]

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("DeepSeek 返回内容中的 JSON object 不完整")


def parse_llm_json(text: str) -> dict:
    """解析 LLM 返回的 JSON object，失败时抛出 ValueError。"""
    cleaned = _strip_code_fence(text)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            result = json.loads(_extract_first_json_object(cleaned))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("LLM JSON 解析失败，原始内容：%s", text)
            raise ValueError(f"DeepSeek 返回内容不是合法 JSON：{exc}") from exc

    if not isinstance(result, dict):
        logger.error("LLM JSON 解析结果不是 object，原始内容：%s", text)
        raise ValueError("DeepSeek 返回 JSON 不是 object")

    return result
