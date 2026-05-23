"""DeepSeek API 调用服务。

本项目只使用 DeepSeek，不做多模型兼容，也不提供通用 LLM Provider 抽象。
"""

from __future__ import annotations

from typing import Any

import httpx

from backend.utils.config import get_deepseek_api_key, get_deepseek_base_url, get_deepseek_model
from backend.utils.logging import get_logger


logger = get_logger("deepseek")


class DeepSeekServiceError(RuntimeError):
    """DeepSeek API 调用失败。"""


def _deepseek_config() -> tuple[str, str, str]:
    """读取 DeepSeek 环境变量配置。"""
    try:
        return get_deepseek_api_key(), get_deepseek_base_url(), get_deepseek_model()
    except RuntimeError as exc:
        raise DeepSeekServiceError(str(exc)) from exc


def chat_with_deepseek(messages: list[dict], temperature: float = 0.2) -> str:
    """调用 DeepSeek Chat Completions 接口，并返回 assistant 文本。"""
    api_key, base_url, model = _deepseek_config()
    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        logger.info("正在调用 DeepSeek API：model=%s, url=%s", model, url)
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:1000]
        raise DeepSeekServiceError(f"DeepSeek API 返回错误：HTTP {exc.response.status_code}，{body}") from exc
    except httpx.HTTPError as exc:
        raise DeepSeekServiceError(f"DeepSeek API 请求失败：{exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise DeepSeekServiceError(f"DeepSeek API 响应结构异常：{response.text[:1000]}") from exc

    if not isinstance(content, str) or not content.strip():
        raise DeepSeekServiceError("DeepSeek API 返回空内容")

    return content.strip()
