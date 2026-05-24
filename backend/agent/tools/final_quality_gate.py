from __future__ import annotations

from .output_validator import ALLOWED_PRIORITIES, ALLOWED_TECHNIQUES, require_fields


REQUIRED_TEST_CASE_FIELDS = [
    "test_id",
    "requirement_id",
    "coverage_item_id",
    "spec_id",
    "technique",
    "title",
    "preconditions",
    "input_data",
    "test_steps",
    "expected_result",
    "standard_ref",
    "priority",
    "status",
]


def run_final_quality_gate(result: dict) -> None:
    """在对外返回前执行最终质量门禁。

    pipeline 中间阶段已经做过局部校验，这里专注于最终交付物：
    至少有 coverage item、design spec、test case，且 test case 能追溯
    到已有 coverage item 和 spec。
    """

    coverage_items = result.get("coverage_items", [])
    test_design_specs = result.get("test_design_specs", [])
    test_cases = result.get("test_cases", [])

    if not isinstance(coverage_items, list):
        raise ValueError("coverage_items must be a list.")
    if not isinstance(test_design_specs, list):
        raise ValueError("test_design_specs must be a list.")
    if not isinstance(test_cases, list):
        raise ValueError("test_cases must be a list.")
    if not coverage_items:
        raise ValueError("At least one coverage_item is required.")
    if not test_design_specs:
        raise ValueError("At least one test_design_spec is required.")
    if not test_cases:
        raise ValueError("At least one test_case is required.")

    coverage_item_ids = {
        str(item.get("coverage_item_id", ""))
        for item in coverage_items
        if isinstance(item, dict)
    }
    spec_ids = {
        str(item.get("spec_id", ""))
        for item in test_design_specs
        if isinstance(item, dict)
    }

    for index, test_case in enumerate(test_cases):
        if not isinstance(test_case, dict):
            raise ValueError(f"test_cases[{index}] must be a dict.")

        require_fields(test_case, REQUIRED_TEST_CASE_FIELDS, f"test_cases[{index}]")

        if not str(test_case.get("expected_result", "")).strip():
            raise ValueError(f"test_cases[{index}].expected_result must not be empty.")
        if test_case.get("status") != "Draft":
            raise ValueError(f"test_cases[{index}].status must be Draft.")
        if test_case.get("technique") not in ALLOWED_TECHNIQUES:
            raise ValueError(f"test_cases[{index}].technique must be EP, BVA, or DT.")
        if test_case.get("priority") not in ALLOWED_PRIORITIES:
            raise ValueError(f"test_cases[{index}].priority must be P1, P2, or P3.")
        if str(test_case.get("coverage_item_id", "")) not in coverage_item_ids:
            raise ValueError(
                f"test_cases[{index}].coverage_item_id does not exist in coverage_items."
            )
        if str(test_case.get("spec_id", "")) not in spec_ids:
            raise ValueError(f"test_cases[{index}].spec_id does not exist in test_design_specs.")
