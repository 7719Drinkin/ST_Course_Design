"""提示词拼接工具。

本模块只负责构造 RAG 生成任务的 DeepSeek messages，不直接调用模型。
"""

from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = (
    "You are a senior software testing expert with strong knowledge of ISTQB, black-box testing, "
    "boundary value analysis, equivalence partitioning, state transition testing, exception scenario "
    "design, security testing, and performance testing. You must use the user requirement and the "
    "RAG-retrieved testing knowledge context to produce strict JSON only."
)


def _chunk_label(index: int) -> str:
    """生成上下文块标题。"""
    return f"[Chunk {index}]"


def _format_context_block(retrieved_chunks: list[dict[str, Any]]) -> str:
    """把 retrieval 结果格式化为 prompt 中的上下文块。"""
    if not retrieved_chunks:
        return "No RAG context is available."

    blocks: list[str] = []
    for index, chunk in enumerate(retrieved_chunks, start=1):
        metadata = chunk.get("metadata") or {}
        section = metadata.get("section") or metadata.get("chapter") or ""
        blocks.append(
            "\n".join(
                [
                    _chunk_label(index),
                    f"source: {metadata.get('source', '')}",
                    f"section: {section}",
                    f"chunk_id: {metadata.get('chunk_id', '')}",
                    "content:",
                    str(chunk.get("content", "")),
                ]
            )
        )
    return "\n\n".join(blocks)


def _json_schema_text(schema: dict[str, Any]) -> str:
    """把 JSON schema 样例格式化为紧凑文本。"""
    return json.dumps(schema, ensure_ascii=False, indent=2)


def build_test_points_prompt(requirement: str, retrieved_chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """构造测试点生成提示词。"""
    output_schema = {
        "requirement": "Original requirement text",
        "context_quality": "high | medium | low",
        "test_objectives": [{"content": "Test objective", "inferred": False}],
        "risks": [{"content": "Risk item", "inferred": False}],
        "test_points": [
            {
                "id": "TP001",
                "title": "Test point title",
                "description": "Test point description",
                "type": "Boundary | Equivalence | StateTransition | Exception | Functional | Security | Performance | Other",
                "priority": "High | Medium | Low",
                "inferred": False,
            }
        ],
        "boundary_scenarios": [{"content": "Boundary scenario", "inferred": False}],
        "exception_scenarios": [{"content": "Exception scenario", "inferred": True}],
    }

    user_prompt = f"""
[User Requirement]
{requirement}

[RAG-Retrieved Testing Knowledge Context]
{_format_context_block(retrieved_chunks)}

[Task]
Analyze the user requirement and generate test objectives, risks, test points, boundary scenarios, and exception scenarios.

[Generation Rules]
1. First identify input domains, constraints, boundaries, state changes, and exception conditions in the requirement.
2. Prefer boundary value analysis and equivalence partitioning.
3. If the requirement involves state changes, add state transition test points.
4. If the requirement involves permissions, sensitive data, or attack surface, add security test points.
5. If the requirement involves response time, concurrency, or capacity, add performance test points.
6. Prefer evidence from the RAG context; do not fabricate standard references or sources.
7. If the context has no direct evidence, you may supplement with general testing expertise, but the corresponding item's inferred field must be true.
8. Do not generate test points unrelated to the requirement.
9. Test point ids must start from TP001 and increase sequentially.
10. priority must be one of: High, Medium, Low.
11. type must be one of: Boundary, Equivalence, StateTransition, Exception, Functional, Security, Performance, Other.
12. Do not output sources. Sources will be added by the backend from retrieval metadata.
13. Write generated business-facing content in the same language as the user requirement.
14. Output only one JSON object. Do not output Markdown. Do not explain. Do not wrap the answer in a ```json code block.

[Inferred Marking Rules]
- If an item can be directly derived from the context or requirement, set inferred=false.
- If an item is added based on general testing expertise, set inferred=true.

[Output JSON Schema]
{_json_schema_text(output_schema)}
""".strip()

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_test_cases_prompt(
    requirement: str,
    test_points: list[dict[str, Any]],
    retrieved_chunks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """构造测试用例生成提示词。"""
    output_schema = {
        "requirement": "Original requirement text",
        "test_cases": [
            {
                "case_id": "TC001",
                "title": "Test case title",
                "precondition": "Precondition",
                "steps": ["Step 1", "Step 2"],
                "expected_result": "Expected result",
                "priority": "High | Medium | Low",
                "type": "Boundary | Equivalence | StateTransition | Exception | Functional | Security | Performance | Other",
                "related_test_point": "TP001",
                "inferred": False,
            }
        ],
    }

    user_prompt = f"""
[User Requirement]
{requirement}

[Generated Test Points]
{json.dumps(test_points, ensure_ascii=False, indent=2)}

[RAG-Retrieved Testing Knowledge Context]
{_format_context_block(retrieved_chunks)}

[Task]
Generate structured test cases based on the user requirement, generated test points, and RAG context.

[Generation Rules]
1. Generate at least one test case for each test point.
2. case_id must start from TC001 and increase sequentially.
3. related_test_point must match an existing TPxxx id.
4. For Boundary test points, prioritize min-1, min, max, and max+1 cases.
5. For Equivalence test points, cover valid and invalid equivalence classes.
6. For StateTransition test points, cover valid and invalid state transitions.
7. For Exception test points, generate negative test cases.
8. Steps must be executable, and expected results must be verifiable.
9. Prefer evidence from the RAG context; do not fabricate standard references or sources.
10. If the context has no direct evidence, you may supplement with general testing expertise, but the corresponding test case's inferred field must be true.
11. priority must be one of: High, Medium, Low.
12. type must be one of: Boundary, Equivalence, StateTransition, Exception, Functional, Security, Performance, Other.
13. Do not output sources. Sources will be added by the backend from retrieval metadata.
14. Write generated business-facing content in the same language as the user requirement.
15. Output only one JSON object. Do not output Markdown. Do not explain. Do not wrap the answer in a ```json code block.

[Inferred Marking Rules]
- If a test case can be directly derived from the context, requirement, or test point, set inferred=false.
- If a test case is added based on general testing expertise, set inferred=true.

[Output JSON Schema]
{_json_schema_text(output_schema)}
""".strip()

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
