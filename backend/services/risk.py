"""风险分析服务。

当前用需求优先级映射 Impact × Likelihood，后续可接入 RAG 风险依据。
"""

from __future__ import annotations

from backend.models import RiskScore
from backend.services.parsing import load_sample_requirements


def _priority_to_risk(priority: str) -> tuple[int, int, str]:
    """把样例优先级转换为影响度、可能性和风险等级。"""
    mapping = {
        "High": (5, 5, "High"),
        "Medium": (3, 3, "Medium"),
        "Low": (2, 2, "Low"),
    }
    return mapping.get(priority, (3, 3, "Medium"))


def analyze_risk(requirement_ids: list[str] | None = None) -> list[RiskScore]:
    """为需求生成风险评分。"""
    wanted = set(requirement_ids or [])
    results: list[RiskScore] = []
    for item in load_sample_requirements():
        if wanted and item["id"] not in wanted:
            continue
        impact, likelihood, level = _priority_to_risk(item.get("priority", "Medium"))
        results.append(
            RiskScore(
                requirement_id=item["id"],
                impact=impact,
                likelihood=likelihood,
                risk_level=level,
                rationale=f"根据样例需求优先级 {item.get('priority', 'Medium')} 生成初始风险评分。",
            )
        )
    return results
