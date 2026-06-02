from __future__ import annotations

"""Agent output validation and final quality gate tests."""

import pytest

from backend.agent.core.models import CoverageItem, TestCaseDraft as CaseDraftModel
from backend.agent.tools.validation.final_quality_gate import run_final_quality_gate
from backend.agent.tools.validation.output_validator import (
    validate_coverage_items,
    validate_model_list,
    validate_requirements,
    validate_risk_analysis,
)


def test_missing_field_fails_in_pydantic_model_wrapper():
    with pytest.raises(ValueError, match="requirements\\[0\\].*description.*Item preview"):
        validate_requirements(
            [
                {
                    "requirement_id": "REQ-AUT-001",
                    "module": "Books",
                    "raw_text": "新增图书时必须填写标题。",
                }
            ]
        )


def test_invalid_technique_fails_in_model_validation():
    item = _valid_result()["coverage_items"][0] | {"technique": "FSM"}

    with pytest.raises(ValueError, match="coverage_items\\[0\\].*technique"):
        validate_coverage_items([item])


def test_model_rejects_invalid_risk_level_mapping():
    risk_item = _valid_result()["risk_analysis"][0] | {
        "impact": 2,
        "likelihood": 3,
        "risk_score": 6,
        "risk_level": "High",
        "test_priority": "P3",
    }

    with pytest.raises(ValueError, match="risk_level does not match risk_score"):
        validate_risk_analysis([risk_item])


def test_risk_score_mismatch_fails_in_model_validation():
    risk_item = _valid_result()["risk_analysis"][0] | {"risk_score": 12}

    with pytest.raises(ValueError, match="risk_score must equal impact \\* likelihood"):
        validate_risk_analysis([risk_item])


def test_model_rejects_invalid_priority_literal():
    test_case = _valid_result()["test_cases"][0] | {"priority": "P0"}

    with pytest.raises(ValueError):
        CaseDraftModel.model_validate(test_case)


def test_model_rejects_non_draft_status():
    test_case = _valid_result()["test_cases"][0] | {"status": "Ready"}

    with pytest.raises(ValueError):
        CaseDraftModel.model_validate(test_case)


def test_output_validator_converts_dict_list_to_models():
    items = validate_model_list(
        [_valid_result()["coverage_items"][0]],
        CoverageItem,
        "coverage_items",
    )

    assert len(items) == 1
    assert isinstance(items[0], CoverageItem)


def test_complete_chain_passes_final_quality_gate():
    run_final_quality_gate(_valid_result())


def test_priority_mismatch_fails_in_final_quality_gate():
    result = _valid_result()
    result["test_cases"][0]["priority"] = "P2"

    with pytest.raises(ValueError, match="priority must match RiskAnalysisItem.test_priority"):
        run_final_quality_gate(result)


def test_missing_coverage_item_id_fails_in_final_quality_gate():
    result = _valid_result()
    result["test_cases"][0]["coverage_item_id"] = "COV-AUT-999-EP-001"

    with pytest.raises(ValueError, match="coverage_item_id not found in coverage_items"):
        run_final_quality_gate(result)


def test_missing_spec_id_fails_in_final_quality_gate():
    result = _valid_result()
    result["test_cases"][0]["spec_id"] = "SPEC-AUT-999-EP-001"

    with pytest.raises(ValueError, match="spec_id does not exist in test_design_specs"):
        run_final_quality_gate(result)


def _valid_result() -> dict:
    return {
        "requirements": [
            {
                "requirement_id": "REQ-AUT-001",
                "module": "Books",
                "raw_text": "新增图书时必须填写标题。",
                "description": "新增图书标题必填。",
            }
        ],
        "analyzed_requirements": [
            {
                "requirement_id": "REQ-AUT-001",
                "module": "Books",
                "description": "新增图书标题必填。",
                "input_fields": ["title"],
                "data_ranges": ["title 非空字符串"],
                "conditions": ["提交新增图书表单"],
                "business_rules": ["标题不能为空"],
                "expected_action": "系统保存图书或返回校验错误。",
            }
        ],
        "risk_analysis": [
            {
                "requirement_id": "REQ-AUT-001",
                "impact": 5,
                "likelihood": 3,
                "risk_score": 15,
                "risk_level": "High",
                "test_priority": "P1",
                "risk_reason": "标题缺失会导致核心新增流程失败。",
            }
        ],
        "coverage_goals": [
            {
                "coverage_goal_id": "CG-AUT-001-001",
                "requirement_id": "REQ-AUT-001",
                "goal": "覆盖标题必填校验。",
                "related_inputs": ["title"],
                "related_conditions": ["提交新增图书表单"],
                "expected_action": "系统拒绝空标题。",
            }
        ],
        "coverage_items": [
            {
                "coverage_item_id": "COV-AUT-001-EP-001",
                "coverage_goal_id": "CG-AUT-001-001",
                "requirement_id": "REQ-AUT-001",
                "technique": "EP",
                "description": "区分标题为空和非空两个等价类。",
                "conditions": ["提交新增图书表单"],
                "data_ranges": ["title 为空", "title 非空"],
                "input_fields": ["title"],
                "expected_action": "系统按等价类返回保存成功或校验错误。",
                "strategy_rationale": "标题必填属于典型有效/无效等价类。",
                "technique_reason": "EP 能直接覆盖必填字段的有效和无效输入。",
            }
        ],
        "test_design_specs": [
            {
                "spec_id": "SPEC-AUT-001-EP-001",
                "coverage_item_id": "COV-AUT-001-EP-001",
                "requirement_id": "REQ-AUT-001",
                "technique": "EP",
                "design_points": [
                    {"class": "invalid", "title": "", "expected": "校验失败"}
                ],
                "standard_ref": "ISO/IEC/IEEE 29119-4 EP",
            }
        ],
        "test_cases": [
            {
                "test_id": "TC-AUT-001-001",
                "requirement_id": "REQ-AUT-001",
                "coverage_item_id": "COV-AUT-001-EP-001",
                "spec_id": "SPEC-AUT-001-EP-001",
                "technique": "EP",
                "title": "新增图书时标题为空应失败",
                "preconditions": ["管理员已登录"],
                "input_data": {"title": ""},
                "test_steps": ["打开新增图书页面", "提交空标题"],
                "expected_result": "系统提示标题不能为空。",
                "standard_ref": "ISO/IEC/IEEE 29119-4 EP",
                "priority": "P1",
                "status": "Draft",
            }
        ],
    }
