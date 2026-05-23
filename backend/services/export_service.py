"""导出服务。"""

from __future__ import annotations

import json
from typing import Any


def _format_value(value: Any, level: int = 0) -> str:
    """把任意生成结果格式化为 Markdown。"""
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            title = str(key).replace("_", " ")
            if isinstance(item, (dict, list)):
                lines.append(f"{'#' * min(level + 2, 6)} {title}")
                lines.append(_format_value(item, level + 1))
            else:
                lines.append(f"- **{title}**: {item}")
        return "\n\n".join(line for line in lines if line)

    if isinstance(value, list):
        if not value:
            return "_无内容_"
        lines = []
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                lines.append(f"{index}.")
                nested = _format_value(item, level + 1)
                lines.append("\n".join(f"   {line}" if line else line for line in nested.splitlines()))
            else:
                lines.append(f"{index}. {item}")
        return "\n".join(lines)

    return json.dumps(value, ensure_ascii=False, indent=2)


def export_markdown(data: dict[str, Any]) -> str:
    """把生成结果导出为 Markdown 文本。"""
    title = data.get("requirement") or "AutoTestDesign 生成结果"
    content = _format_value(data)
    return f"# {title}\n\n{content}\n"
