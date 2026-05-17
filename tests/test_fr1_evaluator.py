"""Tests for the FR1 parse evaluation helper."""

from __future__ import annotations

from pathlib import Path

from scripts.evaluate_fr1_parse import evaluate


ROOT = Path(__file__).resolve().parents[1]


def test_fr1_evaluator_passes_for_baseline_shaped_candidate():
    baseline = ROOT / "tests" / "data" / "aut_15_requirements.json"

    report = evaluate(baseline, baseline)

    assert report["pass"] is True
    assert report["overall_accuracy"] == 1.0
    assert not report["missing_requirements"]


def test_fr1_evaluator_reports_missing_requirements_for_partial_candidate():
    baseline = ROOT / "tests" / "data" / "aut_15_requirements.json"
    partial_candidate = ROOT / "tests" / "data" / "fr1_parse_output_template.json"

    report = evaluate(baseline, partial_candidate)

    assert report["pass"] is False
    assert report["overall_accuracy"] < 0.8
    assert "REQ-AUT-001" in report["missing_requirements"]
