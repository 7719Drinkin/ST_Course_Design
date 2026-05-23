"""FSM service for the frontend Step3 card."""

from __future__ import annotations

from backend.app.models.test_design import FsmResultEntity, FsmTransitionEntity


class FsmService:
    def build(self, requirement_ids: list[str] | None = None) -> FsmResultEntity:
        selected = set(requirement_ids or [])
        has_borrow_flow = not selected or selected.intersection({"REQ-AUT-008", "REQ-AUT-009", "REQ-AUT-012", "REQ-AUT-013"})
        if not has_borrow_flow:
            return FsmResultEntity()

        transitions = [
            FsmTransitionEntity(
                from_="Available",
                to="Borrowed",
                event="POST /api/borrow",
                condition="Book exists, member exists, availableCopies > 0",
            ),
            FsmTransitionEntity(
                from_="Borrowed",
                to="Returned",
                event="PUT /api/return/{recordId}",
                condition="Borrowing record exists and returnDate is null",
            ),
            FsmTransitionEntity(
                from_="Borrowed",
                to="Rejected",
                event="PUT /api/return/{recordId}",
                condition="Borrowing record already returned or missing",
            ),
        ]
        mermaid = "\n".join(
            [
                "stateDiagram-v2",
                "    [*] --> Available",
                "    Available --> Borrowed: POST /api/borrow",
                "    Borrowed --> Returned: PUT /api/return/{recordId}",
                "    Borrowed --> Rejected: invalid return",
            ]
        )
        return FsmResultEntity(
            states=["Available", "Borrowed", "Returned", "Rejected"],
            transitions=transitions,
            all_states=["Available", "Borrowed", "Returned", "Rejected"],
            all_transitions=["Available->Borrowed", "Borrowed->Returned", "Borrowed->Rejected"],
            mermaid=mermaid,
        )


fsm_service = FsmService()

