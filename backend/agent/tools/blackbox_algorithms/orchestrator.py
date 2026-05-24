from __future__ import annotations

from .bva import generate_bva_cases
from .decision_table import generate_dt_cases
from .ep import generate_ep_cases
from .models import normalize_techniques


def generate_deterministic_blackbox_tests(
    requirement_id: str,
    requirement_text: str,
    techniques: list[str] | None = None,
    context: dict | None = None,
) -> dict:
    context = context or {}
    selected_techniques = normalize_techniques(
        techniques or context.get("techniques") or context.get("recommended_techniques")
    )

    data = {
        "coverage_items": [],
        "test_design_specs": [],
        "test_cases": [],
    }
    errors: list[str] = []

    for technique in selected_techniques:
        result = _generate_for_technique(technique, requirement_id, requirement_text, context)
        if not result.get("success"):
            errors.extend(str(error) for error in result.get("errors", []))
            continue
        data["coverage_items"].extend(result["data"].get("coverage_items", []))
        data["test_design_specs"].extend(result["data"].get("test_design_specs", []))
        data["test_cases"].extend(result["data"].get("test_cases", []))

    return {
        "success": True,
        "data": data,
        "metadata": {
            "deterministic": True,
            "techniques": selected_techniques,
            "case_count": len(data["test_cases"]),
        },
        "errors": errors,
    }


def _generate_for_technique(
    technique: str,
    requirement_id: str,
    requirement_text: str,
    context: dict,
) -> dict:
    if technique == "EP":
        return generate_ep_cases(requirement_id, requirement_text, context)
    if technique == "BVA":
        return generate_bva_cases(requirement_id, requirement_text, context)
    if technique == "DT":
        return generate_dt_cases(requirement_id, requirement_text, context)
    return {
        "success": True,
        "data": {
            "coverage_items": [],
            "test_design_specs": [],
            "test_cases": [],
        },
        "metadata": {
            "deterministic": True,
            "techniques": [],
            "case_count": 0,
        },
        "errors": [f"Unsupported technique: {technique}"],
    }
