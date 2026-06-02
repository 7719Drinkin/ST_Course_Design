from __future__ import annotations

"""FSM prompt pipeline contract tests."""

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
                        "condition": "图书可借",
                        "action": "创建借阅记录",
                    },
                    {
                        "from": "BORROWED",
                        "to": "RETURNED",
                        "event": "return",
                        "condition": "借阅记录存在",
                        "action": "关闭借阅记录",
                    },
                ],
                "coverage_paths": ["AVAILABLE -> BORROWED -> RETURNED"],
                "mermaid": "stateDiagram-v2\n    AVAILABLE --> BORROWED : 借阅",
            },
            "test_cases": [
                {
                    "test_id": "TC-AUT-FSM-001",
                    "requirement_id": "REQ-AUT-FSM-001",
                    "coverage_item_id": "COV-AUT-FSM-001",
                    "strategy_id": "STR-AUT-FSM-TRANSITIONS",
                    "technique": "FSM",
                    "title": "可借图书完成借阅和归还",
                    "preconditions": ["图书可借"],
                    "input_data": {"event": "borrow"},
                    "test_steps": ["借阅图书。", "归还图书。"],
                    "expected_result": "模型状态路径为 AVAILABLE -> BORROWED -> RETURNED。",
                    "standard_ref": "ISTQB 状态迁移测试 / 有限状态机测试",
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
                    "raw_text": "会员可以借阅一本可借图书，并在之后归还。",
                }
            ],
            state_candidates=["AVAILABLE", "BORROWED", "RETURNED"],
        )
    )

    assert result.fsm.states == ["AVAILABLE", "BORROWED", "RETURNED"]
    assert result.fsm.transitions[0].from_state == "AVAILABLE"
    assert result.test_cases[0].technique == "FSM"
    assert result.prompts_used[0].name == "fsm_modeling"
    assert "You are an FSM testing agent." in llm_client.prompt
    assert "Return exactly one JSON object" in llm_client.prompt
    assert "Before returning" in llm_client.prompt
