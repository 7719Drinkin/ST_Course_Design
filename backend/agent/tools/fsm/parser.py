from __future__ import annotations

from typing import Any

from .models import FSMModel, FSMState, FSMTransition


LIBRARY_KEYWORDS = (
    "borrow",
    "borrowing",
    "borrowed",
    "/api/borrow",
    "availablecopies",
    "book",
    "member",
    "returndate",
    "recordid",
    "/api/return",
    "return a borrowed",
    "return request",
    "returned book",
    "借书",
    "借阅",
    "还书",
    "归还",
    "可借",
    "已借",
    "已还",
    "图书",
    "会员",
)
OVERDUE_KEYWORDS = ("overdue", "逾期")


def parse_fsm_from_requirement(
    requirement_id: str,
    requirement_text: str,
    context: dict | None = None,
) -> FSMModel:
    """Parse a requirement into a deterministic FSM model without LLM calls.

    LibraryManagementSystem borrowing and return requirements are mapped to a
    stable lifecycle FSM. Requirements that do not expose a recognizable
    domain are mapped to a generic Initial -> Processing -> Success / Failed
    fallback FSM.
    """

    combined_text = _combined_text(requirement_text, context)
    if _is_library_borrowing_flow(combined_text):
        return _library_borrowing_model(requirement_id, combined_text)
    return _fallback_model(requirement_id)


def _library_borrowing_model(requirement_id: str, combined_text: str) -> FSMModel:
    include_overdue = _has_any(combined_text, OVERDUE_KEYWORDS)
    state_specs = [
        ("AVAILABLE", "The book exists and availableCopies is greater than 0."),
        ("BORROWED", "A borrowing record exists and returnDate is null."),
        ("RETURNED", "The borrowing record is closed and returnDate is set."),
    ]
    if include_overdue:
        state_specs.append(("OVERDUE", "The borrowing record is past its dueDate and not returned."))
    state_specs.append(("REJECTED", "The request is rejected because validation or a business rule failed."))

    states = _make_states(state_specs, initial_name="AVAILABLE", terminal_names={"RETURNED", "REJECTED"})
    state_ids = {state.name: state.state_id for state in states}

    transition_specs = [
        (
            "AVAILABLE",
            "BORROWED",
            "POST /api/borrow",
            "book.id exists, member.id exists, availableCopies > 0",
            "HTTP 201; create borrowing record; decrement availableCopies by 1.",
        ),
        (
            "BORROWED",
            "RETURNED",
            "PUT /api/return/{recordId}",
            "recordId exists and returnDate is null",
            "HTTP 200; set returnDate; increment availableCopies by 1.",
        ),
        (
            "RETURNED",
            "AVAILABLE",
            "logical re-borrow availability",
            "record is closed",
            "The book can be borrowed again if availableCopies > 0.",
        ),
    ]

    if include_overdue:
        transition_specs.extend(
            [
                (
                    "BORROWED",
                    "OVERDUE",
                    "due date passes",
                    "current date is after dueDate and returnDate is null",
                    "Mark the borrowing record as overdue for test coverage.",
                ),
                (
                    "OVERDUE",
                    "RETURNED",
                    "PUT /api/return/{recordId}",
                    "overdue record exists",
                    "HTTP 200; set returnDate; increment availableCopies by 1.",
                ),
            ]
        )

    transition_specs.extend(
        [
            (
                "AVAILABLE",
                "REJECTED",
                "POST /api/borrow",
                "availableCopies = 0",
                "HTTP 400; no borrowing record is created.",
            ),
            (
                "AVAILABLE",
                "REJECTED",
                "POST /api/borrow",
                "book.id is missing or not found",
                "HTTP 400.",
            ),
            (
                "AVAILABLE",
                "REJECTED",
                "POST /api/borrow",
                "member.id is missing or not found",
                "HTTP 400.",
            ),
            (
                "BORROWED",
                "REJECTED",
                "PUT /api/return/{recordId}",
                "record already has returnDate set",
                "HTTP 400.",
            ),
            (
                "AVAILABLE",
                "REJECTED",
                "PUT /api/return/{recordId}",
                "recordId is not found",
                "HTTP 400.",
            ),
        ]
    )

    transitions = _make_transitions(requirement_id, transition_specs, state_ids)
    return FSMModel(
        model_id="FSM-MODEL-001",
        requirement_id=requirement_id,
        name="Library Borrowing Lifecycle FSM",
        description="Deterministic FSM for LibraryManagementSystem borrowing and return behavior.",
        states=states,
        transitions=transitions,
        initial_state=state_ids["AVAILABLE"],
    )


def _fallback_model(requirement_id: str) -> FSMModel:
    state_specs = [
        ("INITIAL", "The request or operation has not started."),
        ("PROCESSING", "The system is validating and processing the request."),
        ("SUCCESS", "The operation completed with the expected result."),
        ("FAILED", "The operation failed validation or raised an exception."),
    ]
    states = _make_states(state_specs, initial_name="INITIAL", terminal_names={"SUCCESS", "FAILED"})
    state_ids = {state.name: state.state_id for state in states}
    transitions = _make_transitions(
        requirement_id,
        [
            (
                "INITIAL",
                "PROCESSING",
                "start",
                "request is received",
                "Begin processing the request.",
            ),
            (
                "PROCESSING",
                "SUCCESS",
                "complete",
                "all validation and business rules pass",
                "Produce the expected successful result.",
            ),
            (
                "PROCESSING",
                "FAILED",
                "fail",
                "validation fails or an exception occurs",
                "Reject the request or report failure.",
            ),
        ],
        state_ids,
    )
    return FSMModel(
        model_id="FSM-MODEL-001",
        requirement_id=requirement_id,
        name="Fallback FSM",
        description="Generic deterministic FSM used when no specific business lifecycle is recognized.",
        states=states,
        transitions=transitions,
        initial_state=state_ids["INITIAL"],
    )


def _make_states(
    specs: list[tuple[str, str]],
    initial_name: str,
    terminal_names: set[str],
) -> list[FSMState]:
    return [
        FSMState(
            state_id=_state_id(index),
            name=name,
            description=description,
            is_initial=name == initial_name,
            is_terminal=name in terminal_names,
        )
        for index, (name, description) in enumerate(specs, start=1)
    ]


def _make_transitions(
    requirement_id: str,
    specs: list[tuple[str, str, str, str, str]],
    state_ids: dict[str, str],
) -> list[FSMTransition]:
    return [
        FSMTransition(
            transition_id=_transition_id(index),
            source_state=state_ids[source_name],
            target_state=state_ids[target_name],
            event=event,
            condition=condition,
            action=action,
            requirement_id=requirement_id,
            coverage_item_id=_coverage_item_id(index),
        )
        for index, (source_name, target_name, event, condition, action) in enumerate(specs, start=1)
    ]


def _combined_text(requirement_text: str, context: dict | None) -> str:
    parts = [requirement_text, _context_text(context or {})]
    return " ".join(part for part in parts if part).casefold()


def _context_text(context: dict[str, Any]) -> str:
    values: list[str] = []
    for key in sorted(context):
        values.extend(_value_text(context[key]))
    return " ".join(values)


def _value_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        values: list[str] = []
        for key in sorted(value):
            values.extend(_value_text(value[key]))
        return values
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_value_text(item))
        return values
    return [str(value)]


def _is_library_borrowing_flow(text: str) -> bool:
    return _has_any(text, LIBRARY_KEYWORDS)


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.casefold() in text for keyword in keywords)


def _state_id(index: int) -> str:
    return f"FSM-STATE-{index:03d}"


def _transition_id(index: int) -> str:
    return f"FSM-TRANS-{index:03d}"


def _coverage_item_id(index: int) -> str:
    return f"COV-AUT-FSM-{index:03d}"
