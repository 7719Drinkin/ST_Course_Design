"""测试用例生成服务。

当前是确定性 stub，后续 E 成员可以把 EP / BVA / DT / FSM 算法接到这里。
"""

from __future__ import annotations

from backend.models import CoverageItem, TestCase
from backend.services.coverage import build_coverage_items
from backend.services.risk import analyze_risk

STANDARD_REFS = {
    "EP": "ISO/IEC/IEEE 29119-4 Equivalence Partitioning",
    "BVA": "ISO/IEC/IEEE 29119-4 Boundary Value Analysis",
    "DT": "ISO/IEC/IEEE 29119-4 Decision Table Testing",
    "FSM": "ISO/IEC/IEEE 29119-4 State Transition Testing",
    "ORACLE": "ISO/IEC/IEEE 29119-4 Test Oracle",
}


def generate_test_cases(
    coverage_items: list[CoverageItem] | None = None,
    requirement_ids: list[str] | None = None,
) -> list[TestCase]:
    """根据覆盖项生成测试用例，确保每条用例携带 coverage_item_id。"""
    items = coverage_items or build_coverage_items(requirement_ids=requirement_ids)
    risk_by_req = {risk.requirement_id: risk.risk_level for risk in analyze_risk()}
    cases: list[TestCase] = []
    for index, item in enumerate(items, start=1):
        cases.append(
            TestCase(
                test_id=f"TC-{index:03d}",
                requirement_id=item.requirement_id,
                coverage_item_id=item.coverage_item_id,
                technique=item.technique,
                input_values={"scenario": item.description},
                expected_result=f"系统行为满足覆盖项：{item.description}",
                standard_ref=STANDARD_REFS.get(item.technique, "ISO/IEC/IEEE 29119-4"),
                risk_level=risk_by_req.get(item.requirement_id, "Medium"),
            )
        )
    return cases
