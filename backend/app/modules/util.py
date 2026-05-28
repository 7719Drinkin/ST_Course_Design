"""Pure utility functions shared across modules — ID generation, type conversion, export formatting.

Agent-layer logic (parsing, technique selection, risk scoring) has been removed.
Each service method now carries a TODO describing the Agent call it expects.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
import csv
import io
import json
import re

from .intake_parse.schemas import PromptEvidence, Requirement

# ---------------------------------------------------------------------------
# reference data
# ---------------------------------------------------------------------------

STANDARD_REFS = {
    "EP": "ISO/IEC/IEEE 29119-4 equivalence partitioning",
    "BVA": "ISO/IEC/IEEE 29119-4 boundary value analysis",
    "DT": "ISO/IEC/IEEE 29119-4 decision table testing",
    "FSM": "ISO/IEC/IEEE 29119-4 state transition testing",
}


def standard_ref_for(technique: str) -> str:
    return STANDARD_REFS.get(technique, "ISO/IEC/IEEE 29119 black-box testing")


# ---------------------------------------------------------------------------
# time & id
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index:03d}"


def next_index(existing: list[dict[str, Any]], id_field: str, prefix: str) -> int:
    max_index = 0
    for item in existing:
        value = str(item.get(id_field, ""))
        if not value.startswith(prefix):
            continue
        match = re.search(r"(\d+)$", value)
        if match:
            max_index = max(max_index, int(match.group(1)))
    return max_index + 1


# ---------------------------------------------------------------------------
# text extraction (pure accessor, not Agent-logic)
# ---------------------------------------------------------------------------

def requirement_text(requirement: Requirement | dict[str, Any] | None) -> str:
    if requirement is None:
        return ""
    raw = requirement.model_dump(mode="json") if isinstance(requirement, Requirement) else requirement
    for key in ("text", "raw_text", "description", "title", "content"):
        value = raw.get(key)
        if value:
            return str(value).strip()
    return ""


# ---------------------------------------------------------------------------
# evidence factory
# ---------------------------------------------------------------------------

def evidence(
    session_id: str,
    prompt_name: str,
    target_id: str | None,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    index: int,
    note: str | None = None,
) -> PromptEvidence:
    return PromptEvidence(
        evidence_id=make_id("PE-AUT", index),
        session_id=session_id,
        prompt_name=prompt_name,
        target_id=target_id,
        input=input_data,
        output=output_data,
        note=note or "TODO: replace app-layer placeholder with Agent/B/E integration when available.",
        created_at=now_iso(),
    )


# ---------------------------------------------------------------------------
# collection helpers
# ---------------------------------------------------------------------------

def unique(items: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def unique_numbers(items: list[int | float]) -> list[int | float]:
    result: list[int | float] = []
    seen: set[int | float] = set()
    for item in items:
        value = int(item) if isinstance(item, float) and item.is_integer() else item
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def to_number(value: Any) -> int | float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def to_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json", by_alias=True)
    if isinstance(item, dict):
        return dict(item)
    return {}


def to_dicts(items: list[Any] | None) -> list[dict[str, Any]]:
    return [to_dict(item) for item in items or []]


def coverage_counts(test_cases: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(item.get("coverage_item_id")) for item in test_cases if item.get("coverage_item_id"))


# ---------------------------------------------------------------------------
# export formatting
# ---------------------------------------------------------------------------

def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def csv_bytes(bundle: dict[str, Any]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["artifact_type", "id", "requirement_id", "coverage_item_id", "strategy_id", "text"])
    for item in bundle.get("requirements", []):
        writer.writerow(["requirement", item.get("requirement_id"), item.get("requirement_id"), "", "", requirement_text(item)])
    for item in bundle.get("coverage_items", []):
        writer.writerow([
            "coverage_item",
            item.get("coverage_item_id"),
            item.get("requirement_id"),
            item.get("coverage_item_id"),
            "",
            item.get("description", ""),
        ])
    for item in bundle.get("strategies", []):
        writer.writerow([
            "strategy",
            item.get("strategy_id"),
            "",
            item.get("coverage_item_id"),
            item.get("strategy_id"),
            item.get("reason", ""),
        ])
    for item in bundle.get("test_cases", []):
        writer.writerow([
            "test_case",
            item.get("test_id"),
            item.get("requirement_id"),
            item.get("coverage_item_id"),
            item.get("strategy_id"),
            item.get("expected_result", ""),
        ])
    for item in bundle.get("oracle_results", []):
        writer.writerow([
            "oracle_result",
            item.get("test_id"),
            "",
            "",
            "",
            item.get("expected_result_suggestion", ""),
        ])
    return output.getvalue().encode("utf-8-sig")
