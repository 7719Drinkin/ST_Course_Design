from __future__ import annotations

import json
import re
from typing import Any


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """从模型输出中提取顶层 JSON object。

    兼容纯 JSON、```json fenced block``` 和普通文本夹杂 JSON 的情况。
    顶层只接受 dict，避免 list 结果绕过后续结构校验。
    """

    candidates = [text.strip()]
    candidates.extend(match.strip() for match in _FENCED_JSON_RE.findall(text))
    candidates.extend(_find_json_objects(text))

    for candidate in candidates:
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value

    preview = text[:500]
    raise ValueError(f"Failed to parse JSON object from LLM output. Raw output preview: {preview}")


def _find_json_objects(text: str) -> list[str]:
    """扫描文本中的候选 JSON object 字符串，忽略数组内部对象。"""

    objects: list[str] = []
    start: int | None = None
    depth = 0
    bracket_depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth > 0:
            bracket_depth -= 1
        elif char == "{":
            if bracket_depth > 0 and depth == 0:
                continue
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : index + 1])
                start = None

    return objects
