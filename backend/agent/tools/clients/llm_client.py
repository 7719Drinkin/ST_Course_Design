from __future__ import annotations

import os
from typing import Any

from ..formatting.json_parser import extract_json


class LLMClient:
    """DeepSeek API 的最小异步客户端封装。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        """读取 DeepSeek 配置，延迟创建真实 AsyncOpenAI client。"""

        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self._client: Any | None = None

    async def generate_text(self, prompt: str) -> str:
        """调用 DeepSeek chat completion，返回纯文本内容。"""

        if not self.api_key:
            raise RuntimeError("DeepSeek API key is not configured.")

        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0")),
            max_tokens=384000,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("DeepSeek API returned empty response.")
        return content

    async def generate_json(self, prompt: str) -> dict[str, Any]:
        """调用模型后用 json_parser 提取顶层 JSON object。"""

        text = await self.generate_text(prompt)
        return extract_json(text)

    def _get_client(self) -> Any:
        """懒加载 openai SDK，避免 import 阶段因依赖缺失直接崩溃。"""

        if self._client is not None:
            return self._client

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for DeepSeek API calls.") from exc

        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=1800.0,  # 30 min, 避免 generate_tests 等长阶段被 OpenAI SDK 600s 默认超时截断
        )
        return self._client
