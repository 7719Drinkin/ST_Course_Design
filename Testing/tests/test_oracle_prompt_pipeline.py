from __future__ import annotations

import asyncio

import pytest

from backend.agent.pipeline import AgentPipeline
from backend.agent.tools.validation import validate_oracle_generation


class FakeLlmClient:
    def __init__(self) -> None:
        self.prompt = ""

    async def generate_json(self, prompt: str) -> dict:
        self.prompt = prompt
        return {
            "oracle_results": [
                {
                    "test_id": "TC-AUT-001",
                    "expected_result_suggestion": "借阅请求被拒绝。",
                    "confidence": 0.91,
                    "explanation": "需求说明只有 availableCopies > 0 时才允许借阅。",
                    "needs_review": False,
                },
                {
                    "test_id": "TC-AUT-002",
                    "expected_result_suggestion": "该预期结果需要设计者复核。",
                    "confidence": 0.62,
                    "explanation": "现有上下文没有定义精确的失败响应。",
                    "needs_review": True,
                },
            ]
        }


def test_generate_oracles_uses_oracle_prompt_pipeline():
    llm_client = FakeLlmClient()
    result = asyncio.run(
        AgentPipeline(llm_client=llm_client).generate_oracles(
            test_cases=[
                {
                    "test_id": "TC-AUT-001",
                    "requirement_id": "REQ-AUT-001",
                    "technique": "BVA",
                    "input_data": {"availableCopies": 0},
                    "test_steps": ["提交 availableCopies = 0 的借阅请求。"],
                    "expected_result": "",
                },
                {
                    "test_id": "TC-AUT-002",
                    "requirement_id": "REQ-AUT-002",
                    "technique": "EP",
                    "input_data": {"memberId": "missing"},
                    "test_steps": ["为不存在的会员提交借阅请求。"],
                    "expected_result": "",
                },
            ],
            requirements=[
                {
                    "requirement_id": "REQ-AUT-001",
                    "description": "只有 availableCopies > 0 时借阅才会成功。",
                }
            ],
            source_context_ids=["CTX-001"],
            rag_context="ISTQB 要求预期结果应是可观察、可判定通过或失败的结果。",
        )
    )

    assert [item.test_id for item in result.oracle_results] == ["TC-AUT-001", "TC-AUT-002"]
    assert result.oracle_results[1].needs_review is True
    assert result.prompts_used[0].name == "oracle_generation"
    assert "FR5 测试预言生成 Agent" in llm_client.prompt
    assert "TC-AUT-001" in llm_client.prompt
    assert "CTX-001" in llm_client.prompt
    assert "只输出 JSON。" in llm_client.prompt


def test_oracle_validation_requires_review_for_low_confidence():
    with pytest.raises(ValueError, match="needs_review 必须为 true"):
        validate_oracle_generation(
            {
                "oracle_results": [
                    {
                        "test_id": "TC-AUT-LOW",
                        "expected_result_suggestion": "一个保守的预期结果。",
                        "confidence": 0.4,
                        "explanation": "上下文不足。",
                        "needs_review": False,
                    }
                ]
            }
        )
