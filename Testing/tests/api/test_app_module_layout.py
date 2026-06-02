from __future__ import annotations

import sys
from pathlib import Path

import pytest


fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from main import create_app  # noqa: E402


FRONTEND_ALIGNED_MODULES = {
    "intake_parse",
    "concept_risk",
    "coverage_strategy",
    "test_design",
    "evidence_improve",
    "optimize_export",
}

REMOVED_LEGACY_MODULES = {"requirements", "analysis", "generation", "exports"}


def test_app_modules_match_frontend_six_step_layout():
    module_root = BACKEND / "app" / "modules"
    modules = {
        item.name
        for item in module_root.iterdir()
        if item.is_dir() and item.name != "__pycache__" and any(item.glob("*.py"))
    }

    assert FRONTEND_ALIGNED_MODULES.issubset(modules)
    assert modules.isdisjoint(REMOVED_LEGACY_MODULES)


def test_all_six_module_routes_are_registered():
    app = create_app()
    paths = {route.path for route in app.routes if hasattr(route, "methods")}
    path_counts = {
        path: sum(1 for route in app.routes if getattr(route, "path", None) == path)
        for path in paths
    }

    # intake_parse
    assert "/ingest" in paths
    assert "/ingest/file" in paths
    assert "/parse" in paths
    # concept_risk
    assert "/concepts" in paths
    assert "/risk" in paths
    # coverage_strategy
    assert "/coverage" in paths
    assert "/strategy" in paths
    # test_design
    assert "/generate" in paths
    assert "/fsm" in paths
    assert path_counts["/fsm"] == 1
    assert "/oracle" in paths
    # evidence_improve
    assert "/revisions" in paths
    assert "/regenerate" in paths
    assert "/analysis" in paths
    # optimize_export
    assert "/optimize" in paths
    assert "/export" in paths
