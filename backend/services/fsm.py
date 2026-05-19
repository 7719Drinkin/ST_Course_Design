"""FSM generation service for borrowing and return workflows."""

from __future__ import annotations

from typing import Any


def build_fsm(requirement_ids: list[str] | None = None) -> dict[str, Any]:
    # Kept deterministic until the FSM algorithm module is plugged in.
    transitions = [
        {
            "from": "Available",
            "to": "Borrowed",
            "event": "POST /api/borrow",
            "condition": "book exists, member exists, availableCopies > 0",
        },
        {
            "from": "Available",
            "to": "Rejected",
            "event": "POST /api/borrow",
            "condition": "availableCopies <= 0 or invalid book/member",
        },
        {
            "from": "Borrowed",
            "to": "Returned",
            "event": "PUT /api/return/{recordId}",
            "condition": "borrowing record exists and returnDate is null",
        },
    ]
    return {
        "states": ["Available", "Borrowed", "Returned", "Rejected"],
        "transitions": transitions,
        "coverage": {
            "all_states": ["Available", "Borrowed", "Returned", "Rejected"],
            "all_transitions": [f"{item['from']}->{item['to']}" for item in transitions],
        },
        "mermaid": (
            "stateDiagram-v2\n"
            "    [*] --> Available\n"
            "    Available --> Borrowed : POST /api/borrow [copies > 0]\n"
            "    Available --> Rejected : POST /api/borrow [invalid or unavailable]\n"
            "    Borrowed --> Returned : PUT /api/return/{recordId}"
        ),
    }
