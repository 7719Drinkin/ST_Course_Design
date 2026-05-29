from __future__ import annotations

from typing import Any

from .revision_utils import (
    ChangeSet,
    collection_id_field,
    dedupe_by_id,
    is_deprecated,
    string_list,
    test_case_coverage_ids,
    to_dicts,
)


TARGET_TO_COLLECTION = {
    "requirement": ("requirements", "requirement_id"),
    "parsed_requirement": ("parsed_requirements", "requirement_id"),
    "risk_result": ("risk_results", "target_id"),
    "coverage_item": ("coverage_items", "coverage_item_id"),
    "strategy": ("strategies", "strategy_id"),
    "test_case": ("test_cases", "test_id"),
    "oracle": ("oracle_results", "test_id"),
    "oracle_result": ("oracle_results", "test_id"),
}

STATE_LIST_KEYS = (
    "requirements",
    "parsed_requirements",
    "risk_results",
    "coverage_goals",
    "coverage_items",
    "strategies",
    "test_design_specs",
    "test_cases",
    "oracle_results",
    "prompt_evidence",
)


def workflow_state(current_state: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    state = current_state or {}
    return {key: to_dicts(state.get(key)) for key in STATE_LIST_KEYS}


def revision_impact(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    target_type = str(revision.get("target_type") or "")
    target_id = str(revision.get("target_id") or "")
    after = revision.get("after") if isinstance(revision.get("after"), dict) else {}
    before = revision.get("before") if isinstance(revision.get("before"), dict) else {}
    target_collection = TARGET_TO_COLLECTION.get(target_type)

    affected = affected_ids(target_type, target_id, state)
    updated: dict[str, Any] = {}
    unchanged: dict[str, Any] = {}
    created: dict[str, Any] = {}
    deprecated: dict[str, Any] = {}

    for collection, items in state.items():
        id_field = collection_id_field(collection)
        if not id_field:
            continue
        selected_ids = affected.get(collection, set())
        selected = [item for item in items if str(item.get(id_field) or "") in selected_ids]
        rest = [item for item in items if str(item.get(id_field) or "") not in selected_ids]
        if target_collection and collection == target_collection[0]:
            selected = [_merge_revision_patch(item, target_id, id_field, after) for item in selected]
        if selected:
            updated[collection] = selected
        if rest:
            unchanged[collection] = rest

    if target_collection and not before:
        collection, id_field = target_collection
        created[collection] = [{**after, id_field: target_id}]
        updated.pop(collection, None)

    if is_deprecated(after):
        if target_collection:
            collection, _ = target_collection
            deprecated[collection] = updated.pop(collection, [after])
        related_tests = updated.get("test_cases", [])
        if related_tests:
            deprecated["test_cases"] = related_tests
            updated.pop("test_cases", None)

    if not any((created, updated, unchanged, deprecated)):
        updated[target_type or "unknown"] = [after or revision]

    return created, updated, unchanged, deprecated


def has_revision_scope(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> bool:
    target_type = str(revision.get("target_type") or "")
    target_id = str(revision.get("target_id") or "")
    if impacted_coverage or impacted_tests:
        return True
    if target_type in {"requirement", "parsed_requirement"}:
        return any(
            str(item.get("requirement_id") or "") == target_id
            for item in [*state.get("requirements", []), *state.get("parsed_requirements", [])]
        )
    if target_type == "risk_result":
        return any(
            str(item.get("requirement_id") or item.get("target_id") or "") == target_id
            for item in state.get("risk_results", [])
        )
    if target_type in {"oracle", "oracle_result"}:
        return any(
            str(item.get("test_id") or item.get("oracle_id") or "") == target_id
            for item in state.get("oracle_results", [])
        )
    return False


def impacted_coverage_items(
    revision: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    updated: dict[str, Any],
) -> list[dict[str, Any]]:
    if updated.get("coverage_items"):
        return list(updated["coverage_items"])
    target_type = str(revision.get("target_type") or "")
    target_id = str(revision.get("target_id") or "")
    if target_type == "strategy":
        coverage_ids = {
            str(item.get("coverage_item_id"))
            for item in state.get("strategies", [])
            if item.get("strategy_id") == target_id and item.get("coverage_item_id")
        }
        return [
            item for item in state.get("coverage_items", [])
            if str(item.get("coverage_item_id") or "") in coverage_ids
        ]
    if target_type == "risk_result":
        return [
            item for item in state.get("coverage_items", [])
            if item.get("requirement_id") == target_id or item.get("coverage_item_id") == target_id
        ]
    return []


def impacted_test_cases(
    state: dict[str, list[dict[str, Any]]],
    updated: dict[str, Any],
    deprecated: dict[str, Any],
    impacted_coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected.extend(item for item in updated.get("test_cases", []) if isinstance(item, dict))
    selected.extend(item for item in deprecated.get("test_cases", []) if isinstance(item, dict))
    coverage_ids = {
        str(item.get("coverage_item_id") or "")
        for item in impacted_coverage
        if item.get("coverage_item_id")
    }
    selected.extend(
        item
        for item in state.get("test_cases", [])
        if test_case_coverage_ids(item) & coverage_ids
    )
    return dedupe_by_id(selected, "test_id")


def affected_ids(
    target_type: str,
    target_id: str,
    state: dict[str, list[dict[str, Any]]],
) -> dict[str, set[str]]:
    affected: dict[str, set[str]] = {key: set() for key in state}
    if target_type in {"requirement", "parsed_requirement"}:
        affected["requirements"].add(target_id)
        affected["parsed_requirements"].add(target_id)
        coverage_ids = {
            str(item.get("coverage_item_id"))
            for item in state["coverage_items"]
            if item.get("requirement_id") == target_id and item.get("coverage_item_id")
        }
        affected["coverage_items"].update(coverage_ids)
        affected["risk_results"].add(target_id)
        _mark_related_by_coverage(affected, coverage_ids, state)
        affected["test_cases"].update(
            str(item.get("test_id"))
            for item in state["test_cases"]
            if item.get("requirement_id") == target_id and item.get("test_id")
        )
    elif target_type == "risk_result":
        affected["risk_results"].add(target_id)
        affected["test_cases"].update(
            str(item.get("test_id"))
            for item in state["test_cases"]
            if item.get("requirement_id") == target_id or item.get("coverage_item_id") == target_id
        )
    elif target_type == "coverage_item":
        coverage_ids = {target_id}
        affected["coverage_items"].add(target_id)
        _mark_related_by_coverage(affected, coverage_ids, state)
    elif target_type == "strategy":
        affected["strategies"].add(target_id)
        coverage_ids = {
            str(item.get("coverage_item_id"))
            for item in state["strategies"]
            if item.get("strategy_id") == target_id and item.get("coverage_item_id")
        }
        _mark_related_by_coverage(affected, coverage_ids, state)
        affected["test_cases"].update(
            str(item.get("test_id"))
            for item in state["test_cases"]
            if item.get("strategy_id") == target_id and item.get("test_id")
        )
    elif target_type == "test_case":
        affected["test_cases"].add(target_id)
        affected["oracle_results"].add(target_id)
    elif target_type in {"oracle", "oracle_result"}:
        affected["oracle_results"].add(target_id)
        affected["test_cases"].add(target_id)
    return affected


def selected_coverage_items(
    impact: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = set(string_list((impact.get("affected_ids") or {}).get("coverage_items")))
    if not ids:
        return fallback
    return [item for item in state.get("coverage_items", []) if str(item.get("coverage_item_id") or "") in ids]


def selected_test_cases(
    impact: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ids = set(string_list((impact.get("affected_ids") or {}).get("test_cases")))
    return [item for item in state.get("test_cases", []) if str(item.get("test_id") or "") in ids]


def selected_requirements(
    impact: dict[str, Any],
    state: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ids = set(string_list((impact.get("affected_ids") or {}).get("requirements")))
    if not ids:
        return state.get("parsed_requirements", []) or state.get("requirements", [])
    return [
        item
        for item in [*state.get("parsed_requirements", []), *state.get("requirements", [])]
        if str(item.get("requirement_id") or "") in ids
    ]


def related_requirements(
    state: dict[str, list[dict[str, Any]]],
    revision: dict[str, Any],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirement_ids = {
        str(revision.get("target_id") or "")
        if revision.get("target_type") in {"requirement", "parsed_requirement"}
        else ""
    }
    requirement_ids.update(
        str(item.get("requirement_id"))
        for item in [*impacted_coverage, *impacted_tests]
        if item.get("requirement_id")
    )
    result = [
        item
        for item in [*state.get("requirements", []), *state.get("parsed_requirements", [])]
        if str(item.get("requirement_id") or "") in requirement_ids
    ]
    return dedupe_by_id(result, "requirement_id")


def related_risk_results(
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirement_ids = {
        str(item.get("requirement_id"))
        for item in [*impacted_coverage, *impacted_tests]
        if item.get("requirement_id")
    }
    coverage_ids = {
        str(item.get("coverage_item_id"))
        for item in impacted_coverage
        if item.get("coverage_item_id")
    }
    return [
        item
        for item in state.get("risk_results", [])
        if str(item.get("requirement_id") or item.get("target_id") or "") in requirement_ids | coverage_ids
    ]


def related_strategies(
    state: dict[str, list[dict[str, Any]]],
    impacted_coverage: list[dict[str, Any]],
    impacted_tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage_ids = {
        str(item.get("coverage_item_id"))
        for item in impacted_coverage
        if item.get("coverage_item_id")
    }
    coverage_ids.update(
        str(item.get("coverage_item_id"))
        for item in impacted_tests
        if item.get("coverage_item_id")
    )
    strategy_ids = {
        str(item.get("strategy_id"))
        for item in impacted_tests
        if item.get("strategy_id")
    }
    return [
        item
        for item in state.get("strategies", [])
        if str(item.get("coverage_item_id") or "") in coverage_ids
        or str(item.get("strategy_id") or "") in strategy_ids
    ]


def revision_requirement_text(revision: dict[str, Any], state: dict[str, list[dict[str, Any]]]) -> str:
    after = revision.get("after") if isinstance(revision.get("after"), dict) else {}
    for key in ("text", "raw_text", "description", "content", "title"):
        if after.get(key):
            return str(after[key])
    target_id = str(revision.get("target_id") or "")
    for item in [*state.get("requirements", []), *state.get("parsed_requirements", [])]:
        if str(item.get("requirement_id") or "") != target_id:
            continue
        for key in ("text", "raw_text", "description", "content", "title"):
            if item.get(key):
                return str(item[key])
    return ""


def deprecate_replaced_tests(
    impacted_tests: list[dict[str, Any]],
    changes: ChangeSet,
    revision: dict[str, Any],
) -> list[dict[str, Any]]:
    new_ids = {
        str(item.get("test_id") or "")
        for item in [*changes.created.get("test_cases", []), *changes.updated.get("test_cases", [])]
        if item.get("test_id")
    }
    replacements: list[dict[str, Any]] = []
    for item in impacted_tests:
        test_id = str(item.get("test_id") or "")
        if not test_id or test_id in new_ids:
            continue
        replacements.append(
            {
                **item,
                "status": "Rejected",
                "review_status": "deprecated_by_revision",
                "deprecated_by_revision": revision.get("revision_id"),
            }
        )
    return replacements


def _merge_revision_patch(
    item: dict[str, Any],
    target_id: str,
    id_field: str,
    after: dict[str, Any],
) -> dict[str, Any]:
    if str(item.get(id_field) or "") != target_id:
        return item
    revised = dict(item)
    revised.update(after)
    revised.setdefault(id_field, target_id)
    return revised


def _mark_related_by_coverage(
    affected: dict[str, set[str]],
    coverage_ids: set[str],
    state: dict[str, list[dict[str, Any]]],
) -> None:
    affected["strategies"].update(
        str(item.get("strategy_id"))
        for item in state["strategies"]
        if item.get("coverage_item_id") in coverage_ids and item.get("strategy_id")
    )
    affected["test_cases"].update(
        str(item.get("test_id"))
        for item in state["test_cases"]
        if item.get("coverage_item_id") in coverage_ids and item.get("test_id")
    )
    affected["risk_results"].update(coverage_ids)
