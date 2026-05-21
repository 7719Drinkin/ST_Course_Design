"""覆盖项生成服务。

覆盖项连接需求、测试技术和最终测试用例，是追溯链路的核心节点。
"""

from __future__ import annotations

from backend.models import CoverageItem, ParsedRequirement
from backend.services.parsing import load_sample_requirements, parse_many


def _coverage_id(requirement_id: str, technique: str, index: int) -> str:
    """生成稳定 coverage_item_id。"""
    suffix = requirement_id.replace("REQ-", "")
    return f"COV-{suffix}-{technique}-{index:03d}"


def build_coverage_items(
    parsed_requirements: list[ParsedRequirement] | None = None,
    requirement_ids: list[str] | None = None,
) -> list[CoverageItem]:
    """从解析后需求生成覆盖项。"""
    parsed = parsed_requirements or parse_many(requirement_ids)
    sample_by_id = {item["id"]: item for item in load_sample_requirements()}
    coverage_items: list[CoverageItem] = []
    for req in parsed:
        techniques = sample_by_id.get(req.requirement_id, {}).get("techniques", ["EP"])
        for index, technique in enumerate(techniques, start=1):
            description = f"覆盖 {req.object}：{req.action}"
            coverage_items.append(
                CoverageItem(
                    coverage_item_id=_coverage_id(req.requirement_id, technique, index),
                    requirement_id=req.requirement_id,
                    technique=technique,
                    description=description,
                    original_description=description,
                )
            )
    return coverage_items
