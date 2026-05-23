"""统一日志配置。"""

from __future__ import annotations

import logging
import re
from typing import Any


def configure_logging(level: int = logging.INFO) -> None:
    """配置适合本地调试阅读的默认日志格式。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """获取 backend 命名空间下的 logger。"""
    return logging.getLogger(f"backend.{name}")


def compact_preview(text: str, max_chars: int = 240) -> str:
    """压缩空白字符，并返回固定长度的片段预览。"""
    preview = re.sub(r"\s+", " ", text).strip()
    if len(preview) <= max_chars:
        return preview
    return f"{preview[: max_chars - 3]}..."


def format_retrieval_debug(query: str, results: list[dict[str, Any]]) -> str:
    """构造结构化的检索调试日志块。"""
    lines = [
        "======== 检索调试 ========",
        "",
        "查询：",
        query,
        "",
    ]

    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        score = result.get("score")
        score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "无"
        lines.extend(
            [
                f"第 {index} 条：",
                f"相似度分数：{score_text}",
                f"来源：{metadata.get('source', '')}",
                f"metadata：{metadata}",
                f"片段预览：{compact_preview(str(result.get('content', '')))}",
                "",
            ]
        )

    lines.append("========================")
    return "\n".join(lines)
