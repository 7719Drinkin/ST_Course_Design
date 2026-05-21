"""需求导入与解析服务。

当前使用确定性规则和样例数据，后续可以在这里接入 RAG / LLM 解析。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.models import ParsedRequirement, Requirement

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REQUIREMENTS_PATH = BACKEND_ROOT / "data" / "samples" / "aut_15_requirements.json"
FALLBACK_REQUIREMENTS_PATH = BACKEND_ROOT.parent / "tests" / "data" / "aut_15_requirements.json"


@lru_cache(maxsize=1)
def load_sample_requirements() -> list[dict[str, Any]]:
    """读取 15 条 AUT 需求样例；backend/data 缺失时回退 tests/data。"""
    data_path = SAMPLE_REQUIREMENTS_PATH if SAMPLE_REQUIREMENTS_PATH.exists() else FALLBACK_REQUIREMENTS_PATH
    with data_path.open(encoding="utf-8") as file:
        return json.load(file)


def _sample_to_requirement(item: dict[str, Any]) -> Requirement:
    """把旧样例 JSON 转成轻量 Requirement 模型。"""
    return Requirement(
        requirement_id=item["id"],
        text=item.get("raw_requirement", ""),
        source="aut_15_requirements",
        module=item.get("area", "general"),
    )


def ingest_requirements(source_type: str = "text", content: Any = "") -> dict[str, Any]:
    """导入需求；样例数据需要通过 source_type=sample 显式加载。"""
    if source_type == "sample":
        return {"requirements": [_sample_to_requirement(item) for item in load_sample_requirements()], "errors": []}

    if source_type == "json" and isinstance(content, str) and content.strip():
        try:
            content = json.loads(content)
        except json.JSONDecodeError as exc:
            return {"requirements": [], "errors": [f"JSON 解析失败：{exc.msg}"]}

    if source_type == "json" and isinstance(content, list):
        requirements = [
            Requirement(
                requirement_id=item.get("requirement_id") or item.get("id") or f"REQ-INPUT-{index:03d}",
                text=item.get("text") or item.get("raw_requirement", ""),
                source=item.get("source", "json_input"),
                module=item.get("module") or item.get("area", "general"),
            )
            for index, item in enumerate(content, start=1)
        ]
        return {"requirements": requirements, "errors": []}

    if isinstance(content, str) and content.strip():
        return {
            "requirements": [
                Requirement(
                    requirement_id="REQ-MANUAL-001",
                    text=content.strip(),
                    source="manual_input",
                    module="manual",
                )
            ],
            "errors": [],
        }

    return {"requirements": [], "errors": ["需求内容不能为空；如需加载样例，请设置 source_type 为 sample。"]}


def parse_requirement(requirement_id: str, text: str = "") -> ParsedRequirement:
    """解析单条需求，返回稳定结构化字段。"""
    sample = next((item for item in load_sample_requirements() if item["id"] == requirement_id), None)
    source_text = text or (sample or {}).get("raw_requirement", "")
    action = (sample or {}).get("expected_action") or source_text
    constraints = list((sample or {}).get("conditions", [])) + list((sample or {}).get("data_ranges", []))
    return ParsedRequirement(
        requirement_id=requirement_id,
        actor="API client",
        action=action,
        object=(sample or {}).get("title", "system behavior"),
        constraints=constraints,
        acceptance_criteria=[(sample or {}).get("expected_action", "满足需求描述中的可观察结果。")],
    )


def parse_many(requirement_ids: list[str] | None = None) -> list[ParsedRequirement]:
    """批量解析需求；未传编号时解析全部样例。"""
    ids = requirement_ids or [item["id"] for item in load_sample_requirements()]
    return [parse_requirement(requirement_id) for requirement_id in ids]
