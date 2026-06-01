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
from .store import workflow_store

DEFAULT_SESSION_ID = "SESSION-CURRENT"
DEFAULT_RAG_CONTEXT = "No external RAG context was provided."

STAGE_PARSE = "parse_requirements"
STAGE_RISK = "analyze_risk"
STAGE_COVERAGE = "identify_coverage"
STAGE_STRATEGY = "assign_strategy"
STAGE_GENERATE = "generate_tests"
STAGE_FSM = "generate_fsm"
STAGE_ORACLE = "generate_oracle"

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


def save_requirement_input(
    session_id: str,
    text: str,
    rag_context: str | None = None,
) -> None:
    workflow_store.save_object(
        session_id or DEFAULT_SESSION_ID,
        "requirement_input",
        {
            "requirement_text": text,
            "rag_context": rag_context or "",
            "updated_at": now_iso(),
        },
    )


def stored_requirement_text(session_id: str = DEFAULT_SESSION_ID) -> str:
    payload = workflow_store.get_object(session_id or DEFAULT_SESSION_ID, "requirement_input") or {}
    return str(payload.get("requirement_text") or "").strip()


def stored_rag_context(session_id: str = DEFAULT_SESSION_ID) -> str | None:
    payload = workflow_store.get_object(session_id or DEFAULT_SESSION_ID, "requirement_input") or {}
    context = str(payload.get("rag_context") or "").strip()
    return context or None


def effective_rag_context(session_id: str, rag_context: str | None = None) -> str:
    return (rag_context or stored_rag_context(session_id) or DEFAULT_RAG_CONTEXT).strip()


def resolve_requirement_text(
    *,
    session_id: str = DEFAULT_SESSION_ID,
    explicit_text: str | None = None,
    fallback_payload: Any = None,
) -> str:
    explicit = (explicit_text or "").strip()
    if explicit:
        return explicit
    stored = stored_requirement_text(session_id)
    if stored:
        return stored
    return text_from_payload(fallback_payload)


def text_from_payload(value: Any) -> str:
    parts = _flatten_text(value)
    seen: set[str] = set()
    unique_parts: list[str] = []
    for part in parts:
        text = str(part).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique_parts.append(text)
    return "\n".join(unique_parts)


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


def prompt_records_to_evidence(
    *,
    session_id: str,
    records: Any,
    target_id: str,
    output_data: dict[str, Any],
    note: str,
) -> list[PromptEvidence]:
    prompt_records = normalize_prompt_records(records)
    if not prompt_records:
        return []
    start = next_index(
        workflow_store.get_list(session_id, "prompt_evidence"),
        "evidence_id",
        "PE-AUT",
    )
    return [
        evidence(
            session_id,
            record["prompt_name"],
            record.get("target_id") or target_id,
            record.get("input") or {},
            output_data,
            start + offset,
            note,
        )
        for offset, record in enumerate(prompt_records)
    ]


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


def merge_by_id(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    id_field: str,
) -> list[dict[str, Any]]:
    """Merge collections without duplicating artifacts that share an ID."""

    merged = list(primary)
    positions = {
        str(item.get(id_field)): index
        for index, item in enumerate(merged)
        if item.get(id_field) is not None
    }
    for item in secondary:
        item_id = str(item.get(id_field) or "")
        if item_id and item_id in positions:
            merged[positions[item_id]] = item
        else:
            merged.append(item)
            if item_id:
                positions[item_id] = len(merged) - 1
    return merged


def coverage_ids_from_test_case(test_case: dict[str, Any]) -> set[str]:
    raw = (
        test_case.get("coverage_item_ids")
        or test_case.get("coverage_items")
        or test_case.get("covered_coverage_item_ids")
    )
    if isinstance(raw, list):
        return {str(item) for item in raw if str(item).strip()}
    coverage_id = test_case.get("coverage_item_id")
    return {str(coverage_id)} if coverage_id else set()


def fsm_coverage_items_from_test_cases(test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create explicit coverage rows for FSM test cases so traceability is exportable."""

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for test_case in test_cases:
        if str(test_case.get("technique") or "").upper() != "FSM":
            continue
        for coverage_id in sorted(coverage_ids_from_test_case(test_case)):
            if coverage_id in seen:
                continue
            seen.add(coverage_id)
            items.append(
                {
                    "coverage_item_id": coverage_id,
                    "coverage_goal_id": "",
                    "requirement_id": str(test_case.get("requirement_id") or ""),
                    "technique": "FSM",
                    "description": str(test_case.get("title") or "FSM coverage inferred from test case."),
                    "conditions": [],
                    "data_ranges": [],
                    "input_fields": [],
                    "expected_action": str(test_case.get("expected_result") or ""),
                    "strategy_rationale": "FSM state-transition coverage generated from the FSM model.",
                    "technique_reason": "FSM is used because the behavior depends on lifecycle states and transitions.",
                    "status": "ai_generated",
                    "source": "algorithm",
                }
            )
    return items


def fsm_coverage_summary(fsm: dict[str, Any] | None, test_cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Build document-ready FSM coverage numbers from the exported FSM object."""

    fsm = fsm or {}
    states = [str(item) for item in fsm.get("states", []) if str(item).strip()]
    transitions = fsm.get("transitions", []) if isinstance(fsm.get("transitions"), list) else []
    coverage = fsm.get("coverage") if isinstance(fsm.get("coverage"), dict) else {}
    covered_states = [str(item) for item in coverage.get("all_states", []) if str(item).strip()]
    covered_transitions = [str(item) for item in coverage.get("all_transitions", []) if str(item).strip()]
    fsm_cases = [item for item in test_cases if str(item.get("technique") or "").upper() == "FSM"]

    if fsm_cases and not covered_states:
        covered_states = _covered_fsm_states(states, fsm.get("coverage_paths", []), fsm_cases)
    if fsm_cases and not covered_transitions:
        covered_transitions = _covered_fsm_transitions(transitions, fsm.get("coverage_paths", []), fsm_cases)

    transition_count = len(transitions)
    state_count = len(states)
    return {
        "state_count": state_count,
        "transition_count": transition_count,
        "covered_states": covered_states,
        "covered_transitions": covered_transitions,
        "state_coverage_rate": _coverage_rate(len(set(covered_states)), state_count),
        "transition_coverage_rate": _coverage_rate(len(set(covered_transitions)), transition_count),
        "fsm_test_case_count": len(fsm_cases),
        "mermaid": str(fsm.get("mermaid") or ""),
    }


def _covered_fsm_states(
    states: list[str],
    coverage_paths: Any,
    fsm_cases: list[dict[str, Any]],
) -> list[str]:
    state_set = set(states)
    covered: set[str] = set()
    for path in coverage_paths if isinstance(coverage_paths, list) else []:
        covered.update(_states_from_path(str(path), state_set))
    text = "\n".join(_test_case_text(item) for item in fsm_cases)
    covered.update(state for state in states if state and state in text)
    return sorted(covered)


def _covered_fsm_transitions(
    transitions: list[Any],
    coverage_paths: Any,
    fsm_cases: list[dict[str, Any]],
) -> list[str]:
    normalized = [_transition_signature(item) for item in transitions]
    normalized = [item for item in normalized if item]
    by_pair: dict[tuple[str, str], list[str]] = {}
    for signature in normalized:
        from_state, to_state, _event = signature
        by_pair.setdefault((from_state, to_state), []).append(_format_transition(signature))

    covered: set[str] = set()
    state_set = {item for signature in normalized for item in signature[:2]}
    for path in coverage_paths if isinstance(coverage_paths, list) else []:
        path_states = _states_from_path(str(path), state_set)
        for left, right in zip(path_states, path_states[1:]):
            covered.update(by_pair.get((left, right), []))

    text = "\n".join(_test_case_text(item) for item in fsm_cases)
    for signature in normalized:
        from_state, to_state, event = signature
        if from_state in text and to_state in text:
            covered.add(_format_transition(signature))
            continue
        if event and event in text:
            covered.add(_format_transition(signature))
    return sorted(covered)


def _states_from_path(path: str, state_set: set[str]) -> list[str]:
    parts = [part.strip() for part in re.split(r"\s*->\s*", path) if part.strip()]
    return [part for part in parts if part in state_set]


def _transition_signature(item: Any) -> tuple[str, str, str] | None:
    if hasattr(item, "model_dump"):
        item = item.model_dump(mode="json", by_alias=True)
    if not isinstance(item, dict):
        return None
    from_state = str(item.get("from") or item.get("from_state") or "").strip()
    to_state = str(item.get("to") or "").strip()
    event = str(item.get("event") or "").strip()
    if not from_state or not to_state:
        return None
    return from_state, to_state, event


def _format_transition(signature: tuple[str, str, str]) -> str:
    from_state, to_state, event = signature
    return f"{from_state}->{to_state}" + (f": {event}" if event else "")


def _test_case_text(test_case: dict[str, Any]) -> str:
    return json.dumps(test_case, ensure_ascii=False, default=str)


def _coverage_rate(covered: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(covered / total, 4)


def strategies_from_coverage_items(coverage_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive an explicit strategy table from coverage items when no separate strategy stage exists."""

    strategies: list[dict[str, Any]] = []
    for index, item in enumerate(coverage_items, start=1):
        coverage_id = str(item.get("coverage_item_id") or "")
        if not coverage_id:
            continue
        technique = _first_technique(item)
        strategies.append(
            {
                "strategy_id": f"STR-AUT-{index:03d}",
                "coverage_item_id": coverage_id,
                "technique": technique,
                "standard_ref": standard_ref_for(technique),
                "reason": str(
                    item.get("technique_reason")
                    or item.get("strategy_rationale")
                    or f"{technique} selected for this coverage item."
                ),
                "algorithm_params": {
                    "requirement_id": item.get("requirement_id") or "",
                    "coverage_goal_id": item.get("coverage_goal_id") or "",
                },
            }
        )
    return strategies


def _first_technique(item: dict[str, Any]) -> str:
    technique = item.get("technique")
    if technique:
        return str(technique).upper()
    techniques = item.get("techniques")
    if isinstance(techniques, list) and techniques:
        return str(techniques[0]).upper()
    if isinstance(techniques, str) and techniques:
        return techniques.upper()
    return "EP"


def dedupe_oracle_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one Oracle result per test_id, preferring review-required and higher confidence records."""

    best: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in items:
        test_id = str(item.get("test_id") or "")
        if not test_id:
            continue
        if test_id not in best:
            best[test_id] = item
            order.append(test_id)
            continue
        if _oracle_rank(item) >= _oracle_rank(best[test_id]):
            best[test_id] = item
    return [best[test_id] for test_id in order]


def _oracle_rank(item: dict[str, Any]) -> tuple[int, float, str]:
    needs_review = 1 if item.get("needs_review") else 0
    try:
        confidence = float(item.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return needs_review, confidence, str(item.get("created_at") or item.get("timestamp") or "")


def parse_sse_event(raw_event: str) -> tuple[str, dict[str, Any]]:
    event = "message"
    data_lines: list[str] = []
    for line in raw_event.splitlines():
        if line.startswith("event:"):
            event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
    if not data_lines:
        return event, {}
    try:
        data = json.loads("\n".join(data_lines))
    except json.JSONDecodeError:
        data = {"raw": "\n".join(data_lines)}
    return event, data if isinstance(data, dict) else {"data": data}


def normalize_stage_output(output: Any) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {}
    normalized = dict(output)
    if "prompts_used" in normalized:
        normalized["prompts_used"] = normalize_prompt_records(normalized.get("prompts_used"))
    return normalized


def normalize_prompt_records(records: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in dict_items(records):
        prompt_name = str(item.get("prompt_name") or item.get("name") or "agent_pipeline")
        target_id = item.get("target_id") or item.get("coverage_item_id") or item.get("spec_id")
        input_data = item.get("input") if isinstance(item.get("input"), dict) else {}
        if item.get("prompt") and "prompt" not in input_data:
            input_data = {**input_data, "prompt": item.get("prompt")}
        output_data = item.get("output") if isinstance(item.get("output"), dict) else {}
        normalized = {
            "prompt_name": prompt_name,
            "target_id": str(target_id) if target_id is not None else None,
            "input": input_data,
            "output": output_data,
            "note": str(item.get("note") or ""),
            "created_at": str(item.get("created_at") or now_iso()),
        }
        for key in ("name", "prompt", "coverage_item_id", "spec_id"):
            if key in item:
                normalized[key] = item[key]
        result.append(normalized)
    return result


def dict_items(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [dict(value)]
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if hasattr(item, "model_dump"):
            items.append(item.model_dump(mode="json", by_alias=True))
        elif isinstance(item, dict):
            items.append(dict(item))
    return items


def stage_output_summary(stage: str, output: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"stage": stage}
    for key, value in output.items():
        if key == "prompts_used":
            continue
        if isinstance(value, list):
            summary[f"{key}_count"] = len(value)
        elif isinstance(value, dict):
            summary[f"{key}_keys"] = sorted(str(item) for item in value.keys())
        else:
            summary[key] = value
    return summary


def risk_analysis_to_risk_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        requirement_id = str(item.get("requirement_id") or item.get("target_id") or "")
        if not requirement_id:
            continue
        results.append(
            {
                "target_id": requirement_id,
                "target_type": item.get("target_type") or "requirement",
                "impact": item.get("impact") or 0,
                "likelihood": item.get("likelihood") or 0,
                "risk_score": item.get("risk_score") or 0,
                "risk_level": item.get("risk_level") or "Medium",
                "test_priority": item.get("test_priority") or "P2",
                "reason": item.get("reason") or item.get("risk_reason") or "",
                "evidence": item.get("evidence") or [],
            }
        )
    return results


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


def _flatten_text(value: Any) -> list[str]:
    if value is None:
        return []
    if hasattr(value, "model_dump"):
        return _flatten_text(value.model_dump(mode="json", by_alias=True))
    if isinstance(value, dict):
        preferred = (
            "requirement_text",
            "raw_text",
            "raw_requirement",
            "description",
            "goal",
            "expected_action",
            "title",
            "risk_reason",
            "reason",
        )
        values: list[str] = []
        for key in preferred:
            if key in value:
                values.extend(_flatten_text(value[key]))
        for key, item in value.items():
            if key not in preferred:
                values.extend(_flatten_text(item))
        return values
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_flatten_text(item))
        return values
    if isinstance(value, (str, int, float, bool)):
        return [str(value)]
    return []
