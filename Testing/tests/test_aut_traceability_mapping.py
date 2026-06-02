"""Static checks for AUT pytest traceability mapping."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from tests.aut.traceability import NON_AUTOMATED_DESIGN_CASES, TRACEABILITY, mapped_test_ids


ROOT = Path(__file__).resolve().parents[2]
AUT_TEST_DIR = ROOT / "Testing" / "tests" / "aut"
EXPORT_JSON = ROOT / "localDocs" / "AUT-test" / "result" / "export" / "autotest_export (2).json"


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
    bundle = json.loads(EXPORT_JSON.read_text(encoding="utf-8"))["export_bundle"]
    exported_test_ids = {item["test_id"] for item in bundle["test_cases"]}

    accounted_for = mapped_test_ids() | set(NON_AUTOMATED_DESIGN_CASES)

    assert exported_test_ids <= accounted_for
