"""Static checks for AUT pytest traceability mapping."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tests.aut.traceability import NON_AUTOMATED_DESIGN_CASES, TRACEABILITY, mapped_test_ids


ROOT = Path(__file__).resolve().parents[3]
AUT_TEST_DIR = ROOT / "Testing" / "tests" / "aut"
TRACKED_EXPORT_JSON = ROOT / "Testing" / "tests" / "export" / "autotest_export (2).json"
LOCAL_EXPORT_JSON = ROOT / "localDocs" / "AUT-test" / "result" / "export" / "autotest_export (2).json"


def _aut_test_function_names() -> set[str]:
    names: set[str] = set()
    for test_file in AUT_TEST_DIR.glob("test_*_api.py"):
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                names.add(node.name)
    return names


def test_aut_traceability_mapping_targets_existing_pytest_functions():
    assert set(TRACEABILITY) <= _aut_test_function_names()


def test_aut_traceability_mapping_accounts_for_exported_final_test_cases():
    export_json = TRACKED_EXPORT_JSON if TRACKED_EXPORT_JSON.exists() else LOCAL_EXPORT_JSON
    if not export_json.exists():
        pytest.skip(
            "Export bundle is required for AUT traceability mapping. "
            f"Expected {TRACKED_EXPORT_JSON} or {LOCAL_EXPORT_JSON}."
        )

    bundle = json.loads(export_json.read_text(encoding="utf-8"))["export_bundle"]
    exported_test_ids = {item["test_id"] for item in bundle["test_cases"]}

    accounted_for = mapped_test_ids() | set(NON_AUTOMATED_DESIGN_CASES)

    assert exported_test_ids <= accounted_for
