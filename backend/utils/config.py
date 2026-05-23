"""后端配置。

本项目只使用 DeepSeek API，不做多模型兼容。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parents[1]
CHROMA_DB_DIR = BACKEND_DIR / "chroma_db"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))
DEFAULT_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "testing_standards")


def get_deepseek_api_key() -> str:
    """获取 DeepSeek API Key，缺失时抛出清晰错误。"""
    api_key = os.getenv("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY).strip()
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，请先配置 DeepSeek API Key")
    return api_key


def get_deepseek_base_url() -> str:
    """获取 DeepSeek API base URL。"""
    base_url = os.getenv("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL).strip().rstrip("/")
    if not base_url:
        raise RuntimeError("DEEPSEEK_BASE_URL 不能为空")
    return base_url


def get_deepseek_model() -> str:
    """获取 DeepSeek 模型名称。"""
    model = os.getenv("DEEPSEEK_MODEL", DEEPSEEK_MODEL).strip()
    if not model:
        raise RuntimeError("DEEPSEEK_MODEL 不能为空")
    return model
