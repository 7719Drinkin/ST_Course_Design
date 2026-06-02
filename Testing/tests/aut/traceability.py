"""Traceability mapping from executable AUT pytest cases to AutoTestDesign output."""

from __future__ import annotations

from collections.abc import Mapping

Traceability = Mapping[str, list[str]]


TRACEABILITY: dict[str, dict[str, list[str]]] = {
    "test_list_books_returns_json_array": {
        "test_ids": ["TC-AUT-001-001-EP-001", "TC-AUT-022-001-DT-001"],
        "requirement_ids": ["REQ-AUT-001", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-001-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P3"],
    },
    "test_create_and_get_book_by_id": {
        "test_ids": [
            "TC-AUT-002-001-EP-001",
            "TC-AUT-003-001-EP-001",
            "TC-AUT-003-001-EP-002",
            "TC-AUT-003-001-EP-003",
            "TC-AUT-021-001-EP-001",
            "TC-AUT-022-001-DT-002",
        ],
        "requirement_ids": ["REQ-AUT-002", "REQ-AUT-003", "REQ-AUT-021", "REQ-AUT-022"],
        "coverage_item_ids": [
            "COV-AUT-002-001-EP-001",
            "COV-AUT-003-001-EP-001",
            "COV-AUT-021-001-EP-001",
            "COV-AUT-022-001-DT-001",
        ],
        "techniques": ["EP", "DT"],
        "priorities": ["P2", "P3"],
    },
    "test_get_missing_book_returns_404": {
        "test_ids": ["TC-AUT-022-001-DT-005"],
        "requirement_ids": ["REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-022-001-DT-001"],
        "techniques": ["DT"],
        "priorities": ["P3"],
    },
    "test_update_existing_book_uses_path_id": {
        "test_ids": ["TC-AUT-004-001-EP-001", "TC-AUT-022-001-DT-001"],
        "requirement_ids": ["REQ-AUT-004", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-004-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P2", "P3"],
    },
    "test_update_missing_book_returns_404": {
        "test_ids": ["TC-AUT-004-002-EP-001", "TC-AUT-022-001-DT-005"],
        "requirement_ids": ["REQ-AUT-004", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-004-002-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P2", "P3"],
    },
    "test_delete_existing_book_then_get_returns_404": {
        "test_ids": ["TC-AUT-005-001-EP-001", "TC-AUT-022-001-DT-003"],
        "requirement_ids": ["REQ-AUT-005", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-005-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P3"],
    },
    "test_delete_missing_book_returns_404": {
        "test_ids": ["TC-AUT-005-001-EP-002", "TC-AUT-022-001-DT-005"],
        "requirement_ids": ["REQ-AUT-005", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-005-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P3"],
    },
    "test_book_malformed_json_request_returns_400": {
        "test_ids": [
            "TC-AUT-021-001-EP-002",
            "TC-AUT-021-001-EP-003",
            "TC-AUT-021-001-EP-004",
            "TC-AUT-022-001-DT-004",
        ],
        "requirement_ids": ["REQ-AUT-021", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-021-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P3"],
    },
    "test_list_members_returns_json_array": {
        "test_ids": ["TC-AUT-006-001-EP-001", "TC-AUT-022-001-DT-001"],
        "requirement_ids": ["REQ-AUT-006", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-006-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P3"],
    },
    "test_create_and_get_member_by_id": {
        "test_ids": [
            "TC-AUT-007-001-EP-001",
            "TC-AUT-008-001-EP-001",
            "TC-AUT-008-001-EP-002",
            "TC-AUT-008-001-EP-003",
            "TC-AUT-022-001-DT-002",
        ],
        "requirement_ids": ["REQ-AUT-007", "REQ-AUT-008", "REQ-AUT-022"],
        "coverage_item_ids": [
            "COV-AUT-007-001-EP-001",
            "COV-AUT-008-001-EP-001",
            "COV-AUT-022-001-DT-001",
        ],
        "techniques": ["EP", "DT"],
        "priorities": ["P2", "P3"],
    },
    "test_get_missing_member_returns_404": {
        "test_ids": ["TC-AUT-022-001-DT-005"],
        "requirement_ids": ["REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-022-001-DT-001"],
        "techniques": ["DT"],
        "priorities": ["P3"],
    },
    "test_update_existing_member_uses_path_id": {
        "test_ids": ["TC-AUT-009-001-EP-001", "TC-AUT-022-001-DT-001"],
        "requirement_ids": ["REQ-AUT-009", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-009-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P2", "P3"],
    },
    "test_update_missing_member_returns_404": {
        "test_ids": ["TC-AUT-009-002-EP-001", "TC-AUT-022-001-DT-005"],
        "requirement_ids": ["REQ-AUT-009", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-009-002-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P2", "P3"],
    },
    "test_delete_existing_member_then_get_returns_404": {
        "test_ids": ["TC-AUT-010-001-EP-001", "TC-AUT-022-001-DT-003"],
        "requirement_ids": ["REQ-AUT-010", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-010-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P3"],
    },
    "test_delete_missing_member_returns_404": {
        "test_ids": ["TC-AUT-022-001-DT-005"],
        "requirement_ids": ["REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-022-001-DT-001"],
        "techniques": ["DT"],
        "priorities": ["P3"],
    },
    "test_list_borrowing_records_returns_json_array": {
        "test_ids": ["TC-AUT-011-001-EP-001", "TC-AUT-022-001-DT-001"],
        "requirement_ids": ["REQ-AUT-011", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-011-001-EP-001", "COV-AUT-022-001-DT-001"],
        "techniques": ["EP", "DT"],
        "priorities": ["P3"],
    },
    "test_borrow_available_book_creates_record_and_decrements_copies": {
        "test_ids": [
            "TC-AUT-012-001-DT-001",
            "TC-AUT-012-001-DT-002",
            "TC-AUT-012-001-DT-003",
            "TC-AUT-013-001-EP-001",
            "TC-AUT-013-001-EP-002",
            "TC-AUT-016-001-BVA-002",
            "TC-AUT-023-001-EP-001",
            "TC-AUT-FSM-001",
        ],
        "requirement_ids": ["REQ-AUT-012", "REQ-AUT-013", "REQ-AUT-016", "REQ-AUT-023"],
        "coverage_item_ids": [
            "COV-AUT-012-001-DT-001",
            "COV-AUT-013-001-EP-001",
            "COV-AUT-016-001-BVA-001",
            "COV-AUT-023-001-EP-001",
            "COV-AUT-FSM-001",
        ],
        "techniques": ["DT", "EP", "BVA", "FSM"],
        "priorities": ["P1", "P2"],
    },
    "test_borrow_rejects_unknown_book": {
        "test_ids": ["TC-AUT-014-001-EP-002", "TC-AUT-022-001-DT-004", "TC-AUT-FSM-002"],
        "requirement_ids": ["REQ-AUT-014", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-014-001-EP-001", "COV-AUT-022-001-DT-001", "COV-AUT-FSM-002"],
        "techniques": ["EP", "DT", "FSM"],
        "priorities": ["P2", "P3"],
    },
    "test_borrow_rejects_unknown_member": {
        "test_ids": ["TC-AUT-015-001-EP-002", "TC-AUT-022-001-DT-004", "TC-AUT-FSM-003"],
        "requirement_ids": ["REQ-AUT-015", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-015-001-EP-001", "COV-AUT-022-001-DT-001", "COV-AUT-FSM-003"],
        "techniques": ["EP", "DT", "FSM"],
        "priorities": ["P2", "P3"],
    },
    "test_borrow_rejects_missing_book_id": {
        "test_ids": ["TC-AUT-014-001-EP-001", "TC-AUT-022-001-DT-004", "TC-AUT-FSM-002"],
        "requirement_ids": ["REQ-AUT-014", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-014-001-EP-001", "COV-AUT-022-001-DT-001", "COV-AUT-FSM-002"],
        "techniques": ["EP", "DT", "FSM"],
        "priorities": ["P2", "P3"],
    },
    "test_borrow_rejects_missing_member_id": {
        "test_ids": ["TC-AUT-015-001-EP-001", "TC-AUT-022-001-DT-004", "TC-AUT-FSM-003"],
        "requirement_ids": ["REQ-AUT-015", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-015-001-EP-001", "COV-AUT-022-001-DT-001", "COV-AUT-FSM-003"],
        "techniques": ["EP", "DT", "FSM"],
        "priorities": ["P2", "P3"],
    },
    "test_borrow_rejects_book_with_zero_available_copies": {
        "test_ids": ["TC-AUT-016-001-BVA-001", "TC-AUT-022-001-DT-004", "TC-AUT-FSM-004"],
        "requirement_ids": ["REQ-AUT-016", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-016-001-BVA-001", "COV-AUT-022-001-DT-001", "COV-AUT-FSM-004"],
        "techniques": ["BVA", "DT", "FSM"],
        "priorities": ["P1", "P3"],
    },
    "test_return_borrowed_book_increments_available_copies": {
        "test_ids": [
            "TC-AUT-017-001-DT-001",
            "TC-AUT-018-001-EP-001",
            "TC-AUT-022-001-DT-001",
            "TC-AUT-FSM-006",
        ],
        "requirement_ids": ["REQ-AUT-017", "REQ-AUT-018", "REQ-AUT-022"],
        "coverage_item_ids": [
            "COV-AUT-017-001-DT-001",
            "COV-AUT-018-001-EP-001",
            "COV-AUT-022-001-DT-001",
            "COV-AUT-FSM-006",
        ],
        "techniques": ["DT", "EP", "FSM"],
        "priorities": ["P1", "P3"],
    },
    "test_return_unknown_record_returns_400": {
        "test_ids": ["TC-AUT-019-001-EP-001", "TC-AUT-022-001-DT-004", "TC-AUT-FSM-008"],
        "requirement_ids": ["REQ-AUT-019", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-019-001-EP-001", "COV-AUT-022-001-DT-001", "COV-AUT-FSM-008"],
        "techniques": ["EP", "DT", "FSM"],
        "priorities": ["P3"],
    },
    "test_duplicate_return_is_rejected": {
        "test_ids": ["TC-AUT-020-001-EP-001", "TC-AUT-022-001-DT-004", "TC-AUT-FSM-007"],
        "requirement_ids": ["REQ-AUT-020", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-020-001-EP-001", "COV-AUT-022-001-DT-001", "COV-AUT-FSM-007"],
        "techniques": ["EP", "DT", "FSM"],
        "priorities": ["P2", "P3"],
    },
    "test_borrow_malformed_json_request_returns_400": {
        "test_ids": [
            "TC-AUT-021-001-EP-002",
            "TC-AUT-021-001-EP-003",
            "TC-AUT-021-001-EP-004",
            "TC-AUT-022-001-DT-004",
            "TC-AUT-FSM-005",
        ],
        "requirement_ids": ["REQ-AUT-021", "REQ-AUT-022"],
        "coverage_item_ids": ["COV-AUT-021-001-EP-001", "COV-AUT-022-001-DT-001", "COV-AUT-FSM-005"],
        "techniques": ["EP", "DT", "FSM"],
        "priorities": ["P3"],
    },
}


NON_AUTOMATED_DESIGN_CASES: dict[str, str] = {
    "TC-AUT-023-001-EP-002": "The current AUT borrow API does not accept a client-supplied borrow date.",
    "TC-AUT-023-001-EP-003": "The current AUT borrow API does not accept a client-supplied borrow date.",
    "TC-AUT-023-001-EP-004": "The current AUT borrow API does not accept a client-supplied borrow date.",
}


def get_traceability(test_name: str) -> dict[str, list[str]] | None:
    return TRACEABILITY.get(test_name.split("[", 1)[0])


def mapped_test_ids() -> set[str]:
    return {test_id for metadata in TRACEABILITY.values() for test_id in metadata["test_ids"]}
