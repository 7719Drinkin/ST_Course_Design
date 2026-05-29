from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class RevisionRunnerError(RuntimeError):
    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ChangeSet:
    created: dict[str, Any] = field(default_factory=dict)
    updated: dict[str, Any] = field(default_factory=dict)
    deprecated: dict[str, Any] = field(default_factory=dict)

    def add_created(self, collection: str, items: list[dict[str, Any]]) -> None:
        _add_group(self.created, collection, items)

    def add_updated(self, collection: str, items: list[dict[str, Any]]) -> None:
        _add_group(self.updated, collection, items)

    def set_updated(self, collection: str, value: Any) -> None:
        if value is not None:
            self.updated[collection] = value

    def add_deprecated(self, collection: str, items: list[dict[str, Any]]) -> None:
        _add_group(self.deprecated, collection, items)

    def merge(self, other: "ChangeSet") -> None:
        merge_grouped(self.created, other.created)
        merge_grouped(self.updated, other.updated)
        merge_grouped(self.deprecated, other.deprecated)


@dataclass
class ReentryResult:
    changes: ChangeSet = field(default_factory=ChangeSet)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    pipeline_result: Any | None = None

    def merge(self, other: "ReentryResult") -> None:
        self.changes.merge(other.changes)
        self.evidence.extend(other.evidence)


def collection_id_field(collection: str) -> str | None:
    return {
        "requirements": "requirement_id",
        "parsed_requirements": "requirement_id",
        "risk_results": "target_id",
        "coverage_goals": "coverage_goal_id",
        "coverage_items": "coverage_item_id",
        "strategies": "strategy_id",
        "test_design_specs": "spec_id",
        "test_cases": "test_id",
        "oracle_results": "test_id",
        "prompt_evidence": "evidence_id",
    }.get(collection)


def model_dump_list(items: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        result.append(model_dump_item(item))
    return result


def model_dump_item(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json", by_alias=True)
    return dict(item)


def to_dicts(items: Any) -> list[dict[str, Any]]:
    if items is None or not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump(mode="json", by_alias=True))
        elif isinstance(item, dict):
            result.append(dict(item))
    return result


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, (tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def dedupe_by_id(items: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get(id_field) or "")
        key = item_id or repr(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def test_case_coverage_ids(test_case: dict[str, Any]) -> set[str]:
    values = {
        str(test_case.get("coverage_item_id") or ""),
        *[str(item) for item in test_case.get("coverage_item_ids", []) if item],
    }
    return {item for item in values if item}


def coverage_technique(item: dict[str, Any]) -> str:
    technique = str(item.get("technique") or item.get("strategy") or "").upper()
    if technique in {"EP", "BVA", "DT", "FSM"}:
        return technique
    return "EP"


def bounded_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(5, parsed))


def is_deprecated(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or item.get("review_status") or "").lower()
    return status in {"rejected", "deprecated"}


def make_next_id(prefix: str, items: list[dict[str, Any]], id_field: str) -> str:
    max_index = 0
    marker = f"{prefix}-"
    for item in items:
        value = str(item.get(id_field) or "")
        if not value.startswith(marker):
            continue
        try:
            max_index = max(max_index, int(value.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{max_index + 1:03d}"


def merge_items(existing: list[dict[str, Any]], updates: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    by_id = {str(item.get(id_field) or ""): dict(item) for item in existing}
    for item in updates:
        item_id = str(item.get(id_field) or "")
        if item_id:
            by_id[item_id] = item
    return [item for item in by_id.values() if item]


def mark_revision(items: list[dict[str, Any]], revision: dict[str, Any], status: str) -> None:
    for item in items:
        item["revision_status"] = status
        item["regenerated_from_revision"] = revision.get("revision_id")


def split_created_updated(
    generated: list[dict[str, Any]],
    existing: list[dict[str, Any]],
    id_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    existing_ids = {str(item.get(id_field) or "") for item in existing}
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    for item in generated:
        if str(item.get(id_field) or "") in existing_ids:
            updated.append(item)
        else:
            created.append(item)
    return created, updated


def merge_grouped(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, values in source.items():
        if not values:
            continue
        if not isinstance(values, list):
            target[key] = values
            continue
        target.setdefault(key, [])
        id_field = collection_id_field(key) or "id"
        existing_ids = {
            str(item.get(id_field) or "")
            for item in target[key]
            if isinstance(item, dict)
        }
        for item in values:
            item_id = str(item.get(id_field) or "") if isinstance(item, dict) else ""
            if item_id and item_id in existing_ids:
                target[key] = [
                    item if str(existing.get(id_field) or "") == item_id else existing
                    for existing in target[key]
                ]
            else:
                target[key].append(item)


def prompt_evidence(
    session_id: str,
    prompt_name: str,
    target_id: str,
    prompt_input: dict[str, Any],
    output: dict[str, Any],
    note: str,
) -> dict[str, Any]:
    return {
        "evidence_id": "",
        "session_id": session_id,
        "prompt_name": prompt_name,
        "target_id": target_id,
        "input": prompt_input,
        "output": output,
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def agent_prompt_records_to_evidence(
    session_id: str,
    records: list[Any],
    target_id: str,
    output_summary: dict[str, Any],
    note: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        item = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
        result.append(
            prompt_evidence(
                session_id,
                str(item.get("name") or item.get("prompt_name") or "agent_pipeline"),
                target_id,
                {"prompt": item.get("prompt", ""), **dict(item.get("input") or {})},
                output_summary,
                note,
            )
        )
    return result


def renumber_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        result.append({**item, "evidence_id": f"PE-AUT-{index:03d}"})
    return result


def _add_group(target: dict[str, Any], key: str, values: list[dict[str, Any]]) -> None:
    if values:
        target.setdefault(key, [])
        target[key].extend(values)
