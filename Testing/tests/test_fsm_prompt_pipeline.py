from __future__ import annotations

import asyncio

from backend.agent.pipeline import AgentPipeline


class FakeLlmClient:
    def __init__(self) -> None:
        self.prompt = ""

    async def generate_json(self, prompt: str) -> dict:
        self.prompt = prompt
        return {
            "fsm": {
                "states": ["AVAILABLE", "BORROWED", "RETURNED"],
                "transitions": [
                    {
                        "from": "AVAILABLE",
                        "to": "BORROWED",
                        "event": "borrow",
                        "condition": "book is available",
                        "action": "create borrowing record",
                    },
                    {
                        "from": "BORROWED",
                        "to": "RETURNED",
                        "event": "return",
                        "condition": "borrowing record exists",
                        "action": "close borrowing record",
                    },
                ],
                "coverage_paths": ["AVAILABLE -> BORROWED -> RETURNED"],
                "mermaid": "stateDiagram-v2\n    AVAILABLE --> BORROWED : borrow",
            },
            "test_cases": [
                {
                    "test_id": "TC-AUT-FSM-001",
                    "requirement_id": "REQ-AUT-FSM-001",
                    "coverage_item_id": "COV-AUT-FSM-001",
                    "strategy_id": "STR-AUT-FSM-TRANSITIONS",
                    "technique": "FSM",
                    "title": "Borrow and return available book",
                    "preconditions": ["Book is available"],
                    "input_data": {"event": "borrow"},
                    "test_steps": ["Borrow the book.", "Return the book."],
                    "expected_result": "The modeled state path is AVAILABLE -> BORROWED -> RETURNED.",
                    "standard_ref": "ISTQB state transition testing / finite state machine testing",
                    "risk_level": "Medium",
                    "status": "Draft",
                }
            ],
        }


def test_generate_fsm_uses_fsm_modeling_prompt_pipeline():
    llm_client = FakeLlmClient()
    result = asyncio.run(
        AgentPipeline(llm_client=llm_client).generate_fsm(
            requirements=[
                {
                    "requirement_id": "REQ-AUT-FSM-001",
                    "raw_text": "A member can borrow an available book and later return it.",
                }
            ],
            state_candidates=["AVAILABLE", "BORROWED", "RETURNED"],
        )
    )

    assert result.fsm.states == ["AVAILABLE", "BORROWED", "RETURNED"]
    assert result.fsm.transitions[0].from_state == "AVAILABLE"
    assert result.test_cases[0].technique == "FSM"
    assert result.prompts_used[0].name == "fsm_modeling"
    assert "Output JSON only." in llm_client.prompt
