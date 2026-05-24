from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re


ALLOWED_TECHNIQUES = {"EP", "BVA", "DT"}
DEFAULT_STANDARD_REF = "ISO/IEC/IEEE 29119-4 / ISTQB Black-box Test Design Techniques"
DEFAULT_RISK_LEVEL = 3
STANDARD_REFS = {
    "EP": "ISO/IEC/IEEE 29119-4 equivalence partitioning",
    "BVA": "ISO/IEC/IEEE 29119-4 boundary value analysis",
    "DT": "ISO/IEC/IEEE 29119-4 decision table testing",
}


def safe_id_part(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", str(value).strip()).strip("-")
    return normalized.upper() or "REQ"


def normalize_techniques(techniques: list[str] | str | None) -> list[str]:
    if not techniques:
        return ["EP", "BVA", "DT"]
    if isinstance(techniques, str):
        techniques = [techniques]

    normalized: list[str] = []
    aliases = {
        "EQUIVALENCE PARTITIONING": "EP",
        "EQUIVALENCE_PARTITIONING": "EP",
        "BOUNDARY VALUE ANALYSIS": "BVA",
        "BOUNDARY_VALUE_ANALYSIS": "BVA",
        "DECISION TABLE": "DT",
        "DECISION_TABLE": "DT",
    }
    for technique in techniques:
        value = str(technique).strip().upper()
        value = aliases.get(value, value)
        if value in ALLOWED_TECHNIQUES and value not in normalized:
            normalized.append(value)
    return normalized or ["EP", "BVA", "DT"]


def make_coverage_goal_id(requirement_id: str, technique: str) -> str:
    return f"GOAL-DET-{safe_id_part(requirement_id)}-{technique}"


def make_coverage_item_id(requirement_id: str, technique: str) -> str:
    return f"COV-DET-{safe_id_part(requirement_id)}-{technique}-001"


def make_indexed_coverage_item_id(requirement_id: str, technique: str, index: int) -> str:
    return f"COV-DET-{safe_id_part(requirement_id)}-{technique}-{index:03d}"


def make_spec_id(requirement_id: str, technique: str, index: int = 1) -> str:
    return f"SPEC-DET-{safe_id_part(requirement_id)}-{technique}-{index:03d}"


def make_test_id(requirement_id: str, index: int, technique: str | None = None) -> str:
    technique_part = f"-{safe_id_part(technique)}" if technique else ""
    return f"TC-DET-{safe_id_part(requirement_id)}{technique_part}-{index:03d}"


def standard_ref_for(technique: str) -> str:
    return STANDARD_REFS.get(technique, DEFAULT_STANDARD_REF)


@dataclass(frozen=True)
class DataRange:
    field: str
    min_value: float | int | None = None
    max_value: float | int | None = None
    min_inclusive: bool = True
    max_inclusive: bool = True
    data_type: str = "number"
    source: str = ""

    @property
    def has_boundary(self) -> bool:
        return self.min_value is not None or self.max_value is not None

    @property
    def is_integer(self) -> bool:
        return self.data_type.lower() in {"int", "integer"} or all(
            value is None or float(value).is_integer()
            for value in (self.min_value, self.max_value)
        )


@dataclass(frozen=True)
class BoundaryPoint:
    field: str
    value: float | int
    label: str
    expected_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "label": self.label,
            "expected_valid": self.expected_valid,
        }


@dataclass(frozen=True)
class DecisionRule:
    rule_id: str
    conditions: dict[str, bool]
    expected_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "conditions": dict(self.conditions),
            "expected_action": self.expected_action,
        }


@dataclass(frozen=True)
class ParsedRequirement:
    requirement_id: str
    text: str
    input_fields: list[str] = field(default_factory=list)
    data_ranges: list[DataRange] = field(default_factory=list)
    enum_values: dict[str, list[str]] = field(default_factory=dict)
    conditions: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    expected_action: str = "The system follows the requirement's expected behavior."
    risk_level: int = DEFAULT_RISK_LEVEL
    standard_ref: str = DEFAULT_STANDARD_REF

    def to_requirement_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "module": "deterministic",
            "raw_text": self.text,
            "description": self.text,
        }

    def to_analyzed_requirement_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "module": "deterministic",
            "description": self.text,
            "input_fields": list(self.input_fields),
            "data_ranges": [
                {
                    "field": item.field,
                    "min_value": item.min_value,
                    "max_value": item.max_value,
                    "min_inclusive": item.min_inclusive,
                    "max_inclusive": item.max_inclusive,
                    "data_type": item.data_type,
                    "source": item.source,
                }
                for item in self.data_ranges
            ],
            "conditions": list(self.conditions),
            "business_rules": list(self.business_rules),
            "enum_values": dict(self.enum_values),
            "expected_action": self.expected_action,
        }


@dataclass(frozen=True)
class CoverageItem:
    coverage_item_id: str
    coverage_goal_id: str
    requirement_id: str
    technique: str
    description: str
    conditions: list[str]
    data_ranges: list[DataRange]
    input_fields: list[str]
    expected_action: str
    strategy_rationale: str
    standard_ref: str = DEFAULT_STANDARD_REF

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_item_id": self.coverage_item_id,
            "coverage_goal_id": self.coverage_goal_id,
            "requirement_id": self.requirement_id,
            "technique": self.technique,
            "description": self.description,
            "conditions": list(self.conditions),
            "data_ranges": [
                {
                    "field": item.field,
                    "min_value": item.min_value,
                    "max_value": item.max_value,
                    "min_inclusive": item.min_inclusive,
                    "max_inclusive": item.max_inclusive,
                    "source": item.source,
                }
                for item in self.data_ranges
            ],
            "input_fields": list(self.input_fields),
            "expected_action": self.expected_action,
            "strategy_rationale": self.strategy_rationale,
            "standard_ref": self.standard_ref,
        }


@dataclass(frozen=True)
class GeneratedTestCase:
    test_id: str
    requirement_id: str
    coverage_item_id: str
    spec_id: str
    technique: str
    title: str
    preconditions: list[str]
    input_data: dict[str, Any]
    test_steps: list[str]
    expected_result: str
    risk_level: int = DEFAULT_RISK_LEVEL
    standard_ref: str = DEFAULT_STANDARD_REF
    status: str = "Draft"

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "requirement_id": self.requirement_id,
            "coverage_item_id": self.coverage_item_id,
            "spec_id": self.spec_id,
            "technique": self.technique,
            "title": self.title,
            "preconditions": list(self.preconditions),
            "input_data": dict(self.input_data),
            "test_steps": list(self.test_steps),
            "expected_result": self.expected_result,
            "risk_level": self.risk_level,
            "standard_ref": self.standard_ref,
            "status": self.status,
        }


def build_test_design_specs(
    coverage_items: list[CoverageItem],
    test_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for item in coverage_items:
        related_cases = [
            case
            for case in test_cases
            if case["coverage_item_id"] == item.coverage_item_id
        ]
        if not related_cases:
            continue
        specs.append(
            {
                "spec_id": related_cases[0]["spec_id"],
                "coverage_item_id": item.coverage_item_id,
                "requirement_id": item.requirement_id,
                "technique": item.technique,
                "design_points": [
                    {
                        "test_id": case["test_id"],
                        "title": case["title"],
                        "input_data": case["input_data"],
                        "expected_result": case["expected_result"],
                    }
                    for case in related_cases
                ],
                "standard_ref": standard_ref_for(item.technique),
            }
        )
    return specs


def build_algorithm_output(
    coverage_items: list[CoverageItem],
    test_cases: list[GeneratedTestCase],
    techniques: list[str],
    errors: list[str] | None = None,
) -> dict[str, Any]:
    case_dicts = [item.to_dict() for item in test_cases]
    return {
        "success": True,
        "data": {
            "coverage_items": [item.to_dict() for item in coverage_items],
            "test_design_specs": build_test_design_specs(coverage_items, case_dicts),
            "test_cases": case_dicts,
        },
        "metadata": {
            "deterministic": True,
            "techniques": list(techniques),
            "case_count": len(case_dicts),
        },
        "errors": errors or [],
    }
