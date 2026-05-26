from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from .prompt_registry import PromptRegistry


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptBuilder:
    """从 markdown 模板构造最终发送给 LLM 的 prompt。"""

    def __init__(self, registry: PromptRegistry | None = None) -> None:
        """允许注入 PromptRegistry，便于测试或替换模板目录。"""

        self.registry = registry or PromptRegistry()

    def build(self, name: str, variables: dict[str, Any]) -> str:
        """读取模板并用变量替换 {placeholder}。

        dict/list 会转为缩进 JSON，避免 prompt 中出现 Python repr。
        缺少变量时直接抛 KeyError，让调用方尽早发现模板契约错误。
        """

        template_path = self.registry.get_template_path(name)
        template = template_path.read_text(encoding="utf-8")
        prepared_variables = {key: self._format_value(value) for key, value in variables.items()}

        def replace(match: re.Match[str]) -> str:
            """替换单个模板占位符，并校验变量是否存在。"""

            variable_name = match.group(1)
            if variable_name not in prepared_variables:
                raise KeyError(f"Missing prompt variable: {variable_name}")
            return prepared_variables[variable_name]

        return _PLACEHOLDER_RE.sub(replace, template)

    def _format_value(self, value: Any) -> str:
        """把 prompt 变量转成适合嵌入 markdown 的字符串。"""

        if isinstance(value, BaseModel):
            return json.dumps(value.model_dump(), ensure_ascii=False, indent=2)
        if isinstance(value, (dict, list)):
            return json.dumps(_jsonable(value), ensure_ascii=False, indent=2)
        if value is None:
            return ""
        return str(value)


def _jsonable(value: Any) -> Any:
    """Prompt 边界专用序列化：只把强类型模型显式转成 JSON 数据。"""

    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value
