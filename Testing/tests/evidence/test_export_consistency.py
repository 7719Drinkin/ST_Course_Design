from __future__ import annotations

"""Export consistency and traceability gate tests."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from Testing.scripts.check_export_bundle import analyze_bundle
from backend.agent.pipeline.finalizer import _check_complete_pipeline_sets
from backend.app.modules.optimize_export.schemas import ExportRequest, OptimizeRequest
from backend.app.modules.optimize_export.service import OptimizeExportService, _validate_export_consistency
from backend.app.modules.pipeline_bg import _require_known_spec_ids
from backend.app.modules.store import workflow_store
from backend.app.modules.util import fsm_coverage_summary


def test_export_consistency_blocks_broken_traceability():
    bundle = {
        "requirements": [
            {"requirement_id": "REQ-AUT-001", "description": "Create a book."},
            {"requirement_id": "REQ-AUT-002", "description": "List books."},
        ],
        "risk_results": [
            {"target_id": "REQ-AUT-001", "risk_level": "Medium"},
        ],
        "coverage_items": [
            {"coverage_item_id": "COV-AUT-001-EP-001", "requirement_id": "REQ-AUT-001"},
        ],
        "test_design_specs": [
            {
                "spec_id": "SPEC-AUT-001-EP-001",
                "coverage_item_id": "COV-AUT-001-EP-001",
                "requirement_id": "REQ-AUT-001",
            }
        ],
        "test_cases": [
            {
                "test_id": "TC-AUT-001-001",
                "requirement_id": "REQ-AUT-001",
                "coverage_item_id": "COV-AUT-001-EP-999",
                "spec_id": "SPEC-AUT-001-EP-001",
                "technique": "EP",
            },
            {
                "test_id": "TC-AUT-001-001",
                "requirement_id": "REQ-AUT-001",
                "coverage_item_id": "COV-AUT-001-EP-001",
                "spec_id": "SPEC-AUT-001-EP-001",
                "technique": "EP",
            },
        ],
        "oracle_results": [
            {"test_id": "TC-AUT-001-001"},
        ],
    }

    with pytest.raises(HTTPException) as exc_info:
        _validate_export_consistency(bundle)

    assert exc_info.value.status_code == 409
    errors = exc_info.value.detail["errors"]
    assert any("risk_results missing requirements" in item for item in errors)
    assert any("duplicate test_id" in item for item in errors)
    assert any("unknown coverage_item_id" in item for item in errors)


def test_fsm_coverage_summary_derives_coverage_from_paths_and_test_cases():
    fsm = {
        "states": ["EMPTY", "READY", "BORROWED"],
        "transitions": [
            {"from": "EMPTY", "to": "READY", "event": "seed"},
            {"from": "READY", "to": "BORROWED", "event": "borrow"},
        ],
        "coverage_paths": ["EMPTY -> READY -> BORROWED"],
        "mermaid": "stateDiagram-v2",
    }
    test_cases = [
        {
            "test_id": "TC-AUT-FSM-001",
            "technique": "FSM",
            "title": "Borrow after setup",
            "test_steps": ["Move EMPTY to READY, then borrow to BORROWED."],
        }
    ]

    summary = fsm_coverage_summary(fsm, test_cases)

    assert summary["state_coverage_rate"] == 1.0
    assert summary["transition_coverage_rate"] == 1.0
    assert summary["covered_states"] == ["BORROWED", "EMPTY", "READY"]
    assert summary["fsm_test_case_count"] == 1


def test_export_consistency_allows_explicit_intentionally_uncovered_coverage():
    bundle = {
        "requirements": [{"requirement_id": "REQ-AUT-001"}],
        "risk_results": [{"target_id": "REQ-AUT-001"}],
        "coverage_items": [
            {
                "coverage_item_id": "COV-AUT-001-EP-001",
                "requirement_id": "REQ-AUT-001",
                "coverage_status": "intentionally_uncovered",
            }
        ],
        "test_design_specs": [],
        "test_cases": [],
        "oracle_results": [],
    }

    _validate_export_consistency(bundle)


def test_baseline_analyzer_reports_known_export_failure_classes():
    summary = analyze_bundle(
        {
            "requirements": [{"requirement_id": "REQ-AUT-001"}, {"requirement_id": "REQ-AUT-002"}],
            "risk_results": [{"target_id": "REQ-AUT-001"}],
            "coverage_items": [{"coverage_item_id": "COV-AUT-001-EP-001"}],
            "test_design_specs": [],
            "test_cases": [
                {
                    "test_id": "TC-AUT-001-001",
                    "coverage_item_id": "COV-AUT-001-EP-999",
                    "spec_id": "SPEC-AUT-001-EP-001",
                    "expected_result": "401 Unauthorized",
                },
                {
                    "test_id": "TC-AUT-001-001",
                    "coverage_item_id": "COV-AUT-001-EP-001",
                    "spec_id": "SPEC-AUT-001-EP-001",
                },
            ],
            "oracle_results": [],
            "analysis_results": [{"status": "missing"}],
            "fsm_coverage_summary": {"state_coverage_rate": 0.0, "transition_coverage_rate": 0.0},
        }
    )

    assert summary["risk_missing_count"] == 1
    assert summary["duplicate_test_id_count"] == 1
    assert summary["unknown_coverage_ref_count"] == 1
    assert summary["unknown_coverage_ref_occurrence_count"] == 1
    assert summary["unknown_spec_ref_count"] == 1
    assert summary["missing_oracle_count"] == 1
    assert summary["unsupported_behavior_hits"]["authorization_or_authentication"] >= 1


def test_finalizer_complete_set_check_blocks_oracle_mismatch():
    result = SimpleNamespace(
        analyzed_requirements=[SimpleNamespace(requirement_id="REQ-AUT-001")],
        risk_analysis=[SimpleNamespace(requirement_id="REQ-AUT-001")],
        coverage_items=[SimpleNamespace(coverage_item_id="COV-AUT-001-EP-001")],
        test_design_specs=[SimpleNamespace(coverage_item_id="COV-AUT-001-EP-001")],
        test_cases=[
            SimpleNamespace(
                test_id="TC-AUT-001-001",
                coverage_item_id="COV-AUT-001-EP-001",
            )
        ],
        fsm_test_cases=[],
        all_test_cases=[SimpleNamespace(test_id="TC-AUT-001-001")],
        oracle_results=[],
    )

    with pytest.raises(ValueError, match="oracle_results must match final test cases"):
        _check_complete_pipeline_sets(result)


def test_generate_stage_blocks_test_cases_that_reference_unknown_specs():
    with pytest.raises(ValueError, match="unknown spec_id"):
        _require_known_spec_ids(
            stage="generate_tests",
            valid=[SimpleNamespace(spec_id="SPEC-AUT-019-BVA-001")],
            items=[SimpleNamespace(spec_id="SPEC-AUT-019-001-BVA-001")],
        )


def test_optimize_syncs_review_status_without_overwriting_traceability_ids():
    session_id = "TEST-OPTIMIZE-SNAPSHOT"
    _seed_export_store(session_id)

    OptimizeExportService().optimize(
        OptimizeRequest(
            session_id=session_id,
            objective="set_cover",
            test_cases=[
                _test_case(
                    spec_id="SPEC-AUT-019-001-BVA-001",
                    status="Approved",
                    title="Frontend edited title",
                )
            ],
        )
    )

    stored = workflow_store.get_list(session_id, "test_cases")
    assert stored[0]["spec_id"] == "SPEC-AUT-019-BVA-001"
    assert stored[0]["coverage_item_id"] == "COV-AUT-019-001-BVA-001"
    assert stored[0]["status"] == "Approved"


def test_export_merges_frontend_edits_but_preserves_backend_traceability_ids():
    session_id = "TEST-EXPORT-SNAPSHOT"
    _seed_export_store(session_id)

    bundle = OptimizeExportService().export_bundle(
        ExportRequest(
            session_id=session_id,
            format="json",
            test_case_status="approved_only",
            test_cases=[
                _test_case(
                    spec_id="SPEC-AUT-019-001-BVA-001",
                    status="Approved",
                    title="Frontend edited title",
                )
            ],
        )
    ).model_dump(mode="json")

    assert len(bundle["test_cases"]) == 1
    assert bundle["test_cases"][0]["spec_id"] == "SPEC-AUT-019-BVA-001"
    assert bundle["test_cases"][0]["coverage_item_id"] == "COV-AUT-019-001-BVA-001"
    assert bundle["test_cases"][0]["title"] == "Frontend edited title"


def _seed_export_store(session_id: str) -> None:
    workflow_store.clear_keys(
        session_id,
        [
            "requirements",
            "risk_results",
            "coverage_items",
            "strategies",
            "test_design_specs",
            "test_cases",
            "fsm_test_cases",
            "oracle_results",
            "analysis_results",
            "revisions",
            "prompt_evidence",
            "fsm",
            "optimization_result",
        ],
    )
    workflow_store.save_many(
        session_id,
        "requirements",
        [{"requirement_id": "REQ-AUT-019", "description": "Borrowing updates available copies."}],
        "requirement_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "risk_results",
        [
            {
                "target_id": "REQ-AUT-019",
                "target_type": "requirement",
                "impact": 4,
                "likelihood": 3,
                "risk_score": 12,
                "risk_level": "Medium",
                "test_priority": "P2",
                "reason": "Borrowing is a core workflow.",
                "evidence": [],
            }
        ],
        "target_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "coverage_items",
        [
            {
                "coverage_item_id": "COV-AUT-019-001-BVA-001",
                "coverage_goal_id": "CG-AUT-019-001",
                "requirement_id": "REQ-AUT-019",
                "technique": "BVA",
                "description": "Boundary values for available copies.",
            }
        ],
        "coverage_item_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "test_design_specs",
        [
            {
                "spec_id": "SPEC-AUT-019-BVA-001",
                "coverage_item_id": "COV-AUT-019-001-BVA-001",
                "requirement_id": "REQ-AUT-019",
                "technique": "BVA",
                "design_points": [],
                "standard_ref": "ISO/IEC/IEEE 29119-4 BVA",
            }
        ],
        "spec_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "test_cases",
        [_test_case(spec_id="SPEC-AUT-019-BVA-001", status="Draft")],
        "test_id",
        replace_all=True,
    )
    workflow_store.save_many(
        session_id,
        "oracle_results",
        [
            {
                "test_id": "TC-AUT-019-001",
                "expected_result_suggestion": "Borrow succeeds or fails according to available copies.",
                "confidence": 0.8,
                "explanation": "Matches the expected borrowing behavior.",
                "needs_review": False,
            }
        ],
        "test_id",
        replace_all=True,
    )


def _test_case(
    *,
    spec_id: str,
    status: str,
    title: str = "Borrow at available copy boundary",
) -> dict:
    return {
        "test_id": "TC-AUT-019-001",
        "requirement_id": "REQ-AUT-019",
        "coverage_item_id": "COV-AUT-019-001-BVA-001",
        "spec_id": spec_id,
        "technique": "BVA",
        "title": title,
        "preconditions": ["Book exists"],
        "input_data": {"availableCopies": 1},
        "test_steps": ["Submit a borrow request."],
        "expected_result": "Borrow succeeds.",
        "standard_ref": "ISO/IEC/IEEE 29119-4 BVA",
        "risk_level": "Medium",
        "status": status,
    }
