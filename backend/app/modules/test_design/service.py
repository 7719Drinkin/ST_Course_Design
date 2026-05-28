"""Step 4 业务逻辑：测试设计、FSM 状态迁移与 Oracle 审查。"""

from __future__ import annotations

from typing import Any

from ..store import workflow_store
from ..util import evidence, next_index, requirement_text as extract_requirement_text, to_dicts
from .schemas import (
    FsmRequest,
    FsmResponse,
    FsmResult,
    FsmTransition,
    GenerateRequest,
    GenerateResponse,
    OracleRequest,
    OracleResult,
    OracleResponse,
    TestCase,
)

try:
    from backend.agent.pipeline import AgentPipeline
    from backend.agent.tools.fsm import generate_fsm_tests
except ModuleNotFoundError:
    from agent.pipeline import AgentPipeline
    from agent.tools.fsm import generate_fsm_tests


class TestDesignService:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """运行 B 侧测试设计 Agent，生成 EP/BVA/DT 测试设计与用例。"""

        return GenerateResponse(
            test_design_specs=[],
            test_cases=[],
            prompts_used=[],
        )

    async def fsm(self, request: FsmRequest) -> FsmResponse:
        """通过 LLM/Prompt pipeline 生成 FR4 FSM 模型、覆盖路径和测试用例。"""

        requirement_id, requirement_text, context = _fsm_source(request)
        try:
            result = await AgentPipeline().generate_fsm(
                requirements=_fsm_requirements(requirement_id, requirement_text, context),
                parsed_requirements=context.get("parsed_requirements", []),
                coverage_items=context.get("coverage_items", []),
                state_candidates=context.get("state_candidates", []),
                rag_context=_joined_context_text(context),
            )
            fsm = _to_prompt_fsm_result(result.fsm.model_dump(mode="json", by_alias=True))
            test_cases = [
                _to_test_case(item.model_dump(mode="json", by_alias=True))
                for item in result.test_cases
            ]
            fsm_coverage_items = _coverage_items_from_test_cases(test_cases)
            prompt_evidence = _prompt_records_to_evidence(
                request.session_id,
                requirement_id,
                result.prompts_used,
                _fsm_output_summary(fsm, test_cases),
                "FR4 FSM 由 fsm_modeling LLM/Prompt pipeline 生成。",
            )
        except Exception as exc:
            fsm, test_cases, fsm_coverage_items, prompt_evidence = _deterministic_fsm_fallback(
                request,
                requirement_id,
                requirement_text,
                context,
                exc,
            )

        workflow_store.save_object(request.session_id, "fsm", fsm)
        workflow_store.save_many(request.session_id, "test_cases", test_cases, "test_id")
        workflow_store.save_many(request.session_id, "coverage_items", fsm_coverage_items, "coverage_item_id")
        workflow_store.save_many(request.session_id, "prompt_evidence", prompt_evidence, "evidence_id")

        return FsmResponse(
            session_id=request.session_id,
            fsm=fsm,
            test_cases=test_cases,
            prompt_evidence=prompt_evidence,
        )

    async def oracle(self, request: OracleRequest) -> OracleResponse:
        """通过 FR5 Oracle Agent 审查或生成测试用例 expected_result。"""

        test_cases = _oracle_test_cases(request)
        requirements = _oracle_requirements(request, test_cases)
        source_context_ids = request.source_context_ids or []

        try:
            result = await AgentPipeline().generate_oracles(
                test_cases=test_cases,
                requirements=requirements,
                source_context_ids=source_context_ids,
                rag_context=_joined_context_text({"requirements": requirements}),
            )
            oracle_results = [
                _to_oracle_result(item.model_dump(mode="json", by_alias=True))
                for item in result.oracle_results
            ]
            prompt_evidence = _oracle_prompt_records_to_evidence(
                request.session_id,
                result.prompts_used,
                [item.test_id for item in oracle_results],
                _oracle_output_summary(oracle_results),
                "FR5 Oracle 由 oracle_generation LLM/Prompt pipeline 生成。",
            )
        except Exception as exc:
            oracle_results, prompt_evidence = _deterministic_oracle_fallback(
                request,
                test_cases,
                requirements,
                source_context_ids,
                exc,
            )

        workflow_store.save_many(request.session_id, "test_cases", request.test_cases, "test_id")
        workflow_store.save_many(request.session_id, "oracle_results", oracle_results, "test_id")
        workflow_store.save_many(request.session_id, "prompt_evidence", prompt_evidence, "evidence_id")

        return OracleResponse(
            session_id=request.session_id,
            oracle_results=oracle_results,
            prompt_evidence=prompt_evidence,
        )


def _oracle_test_cases(request: OracleRequest) -> list[dict[str, Any]]:
    return to_dicts(request.test_cases)


def _oracle_requirements(
    request: OracleRequest,
    test_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    explicit_requirements = to_dicts(request.requirements)
    if explicit_requirements:
        return explicit_requirements

    requirement_ids = _requirement_ids_from_test_cases(test_cases)
    requirements = workflow_store.get_list(
        request.session_id,
        "requirements",
        requirement_ids or None,
        "requirement_id",
    )
    parsed_requirements = workflow_store.get_list(
        request.session_id,
        "parsed_requirements",
        requirement_ids or None,
        "requirement_id",
    )
    return _merge_by_requirement_id([*requirements, *parsed_requirements])


def _requirement_ids_from_test_cases(test_cases: list[dict[str, Any]]) -> list[str]:
    return _dedupe(
        [
            str(item.get("requirement_id") or "").strip()
            for item in test_cases
            if str(item.get("requirement_id") or "").strip()
        ]
    )


def _merge_by_requirement_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        requirement_id = str(item.get("requirement_id") or "").strip()
        key = requirement_id or repr(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _to_oracle_result(item: dict[str, Any]) -> OracleResult:
    confidence = _bounded_confidence(item.get("confidence"), 0.5)
    return OracleResult(
        test_id=str(item.get("test_id") or ""),
        expected_result_suggestion=str(
            item.get("expected_result_suggestion") or "预期结果需要人工复核。"
        ),
        confidence=confidence,
        explanation=str(item.get("explanation") or "Oracle 结果缺少解释，已标记复核。"),
        needs_review=bool(item.get("needs_review", False)) or confidence < 0.7,
    )


def _deterministic_oracle_fallback(
    request: OracleRequest,
    test_cases: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
    source_context_ids: list[str],
    failure: Exception,
) -> tuple[list[OracleResult], list[Any]]:
    oracle_results = [
        _fallback_oracle_result(index, test_case, requirements)
        for index, test_case in enumerate(test_cases, start=1)
    ]
    prompt_evidence = [
        evidence(
            request.session_id,
            "oracle_generation_fallback",
            "oracle_results",
            {
                "test_ids": [item.get("test_id") for item in test_cases],
                "requirement_ids": _requirement_ids_from_test_cases(test_cases),
                "source_context_ids": source_context_ids,
            },
            _oracle_output_summary(oracle_results),
            next_index(
                workflow_store.get_list(request.session_id, "prompt_evidence"),
                "evidence_id",
                "PE-AUT",
            ),
            f"oracle_generation prompt 执行失败，已使用 FR5 确定性 Oracle 兜底：{failure}",
        )
    ]
    return oracle_results, prompt_evidence


def _fallback_oracle_result(
    index: int,
    test_case: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> OracleResult:
    test_id = str(test_case.get("test_id") or f"TC-AUT-ORACLE-{index:03d}")
    requirement = _matching_requirement(test_case, requirements)
    existing_expected = str(test_case.get("expected_result") or "").strip()
    requirement_expected = _requirement_expected_text(requirement)

    if existing_expected:
        confidence = 0.76 if requirement else 0.66
        explanation = (
            "沿用测试用例已有 expected_result，并结合匹配需求复核。"
            if requirement
            else "沿用测试用例已有 expected_result；未找到匹配需求，需人工确认。"
        )
        suggestion = existing_expected
    elif requirement_expected:
        confidence = 0.74
        explanation = "根据 requirement_id 匹配到的需求行为生成预期结果。"
        suggestion = requirement_expected
    else:
        confidence = 0.5
        explanation = "缺少已有 expected_result 和明确需求依据，需人工补充预期结果。"
        suggestion = _generic_oracle_suggestion(test_case)

    return OracleResult(
        test_id=test_id,
        expected_result_suggestion=suggestion,
        confidence=confidence,
        explanation=explanation,
        needs_review=confidence < 0.7,
    )


def _matching_requirement(
    test_case: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> dict[str, Any] | None:
    requirement_id = str(test_case.get("requirement_id") or "").strip()
    if not requirement_id:
        return None
    for requirement in requirements:
        if str(requirement.get("requirement_id") or "").strip() == requirement_id:
            return requirement
    return None


def _requirement_expected_text(requirement: dict[str, Any] | None) -> str:
    if not requirement:
        return ""
    for key in ("expected_action", "expected_result", "description", "raw_text", "text", "title"):
        value = requirement.get(key)
        if value:
            return str(value).strip()
    return ""


def _generic_oracle_suggestion(test_case: dict[str, Any]) -> str:
    title = str(test_case.get("title") or "").strip()
    steps = test_case.get("test_steps") if isinstance(test_case.get("test_steps"), list) else []
    if title:
        return f"执行“{title}”后，系统应产生与需求一致的可观察结果；具体 expected_result 需要人工复核。"
    if steps:
        return "执行测试步骤后，系统应产生与需求一致的可观察结果；具体 expected_result 需要人工复核。"
    return "系统应产生与需求一致的可观察结果；具体 expected_result 需要人工复核。"


def _bounded_confidence(value: Any, default: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, confidence))


def _oracle_prompt_records_to_evidence(
    session_id: str,
    records: list[Any],
    test_ids: list[str],
    output_summary: dict[str, Any],
    note: str,
) -> list[Any]:
    start_index = next_index(
        workflow_store.get_list(session_id, "prompt_evidence"),
        "evidence_id",
        "PE-AUT",
    )
    prompt_evidence: list[Any] = []
    for offset, record in enumerate(records):
        item = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
        prompt_name = str(item.get("name") or item.get("prompt_name") or "oracle_generation")
        prompt_evidence.append(
            evidence(
                session_id,
                prompt_name,
                "oracle_results",
                {
                    "test_ids": test_ids,
                    "prompt": item.get("prompt", ""),
                },
                output_summary,
                start_index + offset,
                note,
            )
        )
    return prompt_evidence


def _oracle_output_summary(oracle_results: list[OracleResult]) -> dict[str, Any]:
    return {
        "oracle_result_count": len(oracle_results),
        "needs_review_count": sum(1 for item in oracle_results if item.needs_review),
        "low_confidence_count": sum(1 for item in oracle_results if item.confidence < 0.7),
    }


def _deterministic_fsm_fallback(
    request: FsmRequest,
    requirement_id: str,
    requirement_text: str,
    context: dict[str, Any],
    failure: Exception,
) -> tuple[FsmResult, list[TestCase], list[dict[str, Any]], list[Any]]:
    """LLM pipeline 不可用或返回非法 JSON 时，回退到确定性 FSM 生成器。"""

    result = generate_fsm_tests(
        requirement_id=requirement_id,
        requirement_text=requirement_text,
        context=context,
        strategies=request.strategies,
        max_depth=request.max_depth,
    )
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    fsm = _to_fsm_result(data)
    test_cases = [_to_test_case(item) for item in data.get("test_cases", [])]
    fsm_coverage_items = _to_workflow_coverage_items(data.get("coverage_items", []))

    prompt_evidence = [
        evidence(
            request.session_id,
            "fsm_generation_fallback",
            requirement_id,
            {
                "requirement_id": requirement_id,
                "requirement_text": requirement_text,
                "state_candidates": request.state_candidates or [],
                "strategies": request.strategies,
                "max_depth": request.max_depth,
            },
            _fsm_output_summary(fsm, test_cases),
            next_index(
                workflow_store.get_list(request.session_id, "prompt_evidence"),
                "evidence_id",
                "PE-AUT",
            ),
            f"fsm_modeling prompt 执行失败，已使用 FR4 确定性 FSM 生成器兜底：{failure}",
        )
    ]
    return fsm, test_cases, fsm_coverage_items, prompt_evidence


def _fsm_requirements(
    requirement_id: str,
    requirement_text: str,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    requirements = context.get("requirements", [])
    if requirements:
        return requirements
    return [
        {
            "requirement_id": requirement_id,
            "raw_text": requirement_text,
            "description": requirement_text,
        }
    ]


def _prompt_records_to_evidence(
    session_id: str,
    requirement_id: str,
    records: list[Any],
    output_summary: dict[str, Any],
    note: str,
) -> list[Any]:
    start_index = next_index(
        workflow_store.get_list(session_id, "prompt_evidence"),
        "evidence_id",
        "PE-AUT",
    )
    prompt_evidence: list[Any] = []
    for offset, record in enumerate(records):
        item = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
        prompt_name = str(item.get("name") or item.get("prompt_name") or "fsm_modeling")
        target_id = str(item.get("coverage_item_id") or item.get("spec_id") or requirement_id)
        prompt_evidence.append(
            evidence(
                session_id,
                prompt_name,
                target_id,
                {
                    "requirement_id": requirement_id,
                    "prompt": item.get("prompt", ""),
                },
                output_summary,
                start_index + offset,
                note,
            )
        )
    return prompt_evidence


def _fsm_output_summary(fsm: FsmResult, test_cases: list[TestCase]) -> dict[str, Any]:
    return {
        "state_count": len(fsm.states),
        "transition_count": len(fsm.transitions),
        "test_case_count": len(test_cases),
        "coverage_path_count": len(fsm.coverage_paths),
    }


def _to_prompt_fsm_result(data: dict[str, Any]) -> FsmResult:
    states = [str(item) for item in data.get("states", []) if str(item).strip()]
    transitions: list[FsmTransition] = []
    transition_labels: list[str] = []
    for item in data.get("transitions", []):
        if not isinstance(item, dict):
            continue
        from_state = str(item.get("from") or item.get("from_state") or "").strip()
        to_state = str(item.get("to") or item.get("target_state") or "").strip()
        if not from_state or not to_state:
            continue
        event = str(item.get("event") or "").strip()
        transitions.append(
            FsmTransition(
                from_state=from_state,
                to=to_state,
                event=event,
                condition=str(item.get("condition") or "").strip(),
                action=str(item.get("action") or "").strip(),
            )
        )
        transition_labels.append(
            " -> ".join(part for part in [from_state, to_state, event] if part)
        )

    return FsmResult(
        states=states,
        transitions=transitions,
        coverage_paths=[str(item) for item in data.get("coverage_paths", []) if str(item).strip()],
        coverage={
            "all_states": states,
            "all_transitions": transition_labels,
        },
        mermaid=str(data.get("mermaid") or ""),
    )


def _coverage_items_from_test_cases(test_cases: list[TestCase]) -> list[dict[str, Any]]:
    coverage_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, case in enumerate(test_cases, start=1):
        item = case.model_dump(mode="json", by_alias=True)
        coverage_item_id = str(item.get("coverage_item_id") or f"COV-AUT-FSM-{index:03d}")
        if coverage_item_id in seen:
            continue
        seen.add(coverage_item_id)
        coverage_items.append(
            {
                "coverage_item_id": coverage_item_id,
                "coverage_goal_id": f"CG-AUT-FSM-{index:03d}",
                "requirement_id": str(item.get("requirement_id") or "REQ-AUT-FSM"),
                "technique": "FSM",
                "conditions": list(item.get("covered_transitions") or item.get("test_steps") or []),
                "data_ranges": [],
                "input_fields": list(item.get("covered_states") or []),
                "expected_action": str(item.get("expected_result") or "执行 FSM 状态迁移路径。"),
                "strategy_rationale": str(item.get("strategy_id") or "FSM 状态/迁移覆盖"),
                "technique_reason": "具有状态相关行为，适合使用 FSM 状态迁移测试覆盖。",
                "status": "ai_generated",
            }
        )
    return coverage_items


def _fsm_source(request: FsmRequest) -> tuple[str, str, dict[str, Any]]:
    requirement_ids = _requested_requirement_ids(request)
    requirements = _request_or_store_items(
        request.session_id,
        "requirements",
        to_dicts(request.requirements),
        requirement_ids,
    )
    parsed_requirements = _request_or_store_items(
        request.session_id,
        "parsed_requirements",
        to_dicts(request.parsed_requirements),
        requirement_ids,
    )
    coverage_items = _request_or_store_items(
        request.session_id,
        "coverage_items",
        to_dicts(request.coverage_items),
        requirement_ids,
    )

    context = {
        "requirements": requirements,
        "parsed_requirements": parsed_requirements,
        "coverage_items": coverage_items,
        "state_candidates": request.state_candidates or [],
    }

    if request.requirement_id or request.requirement_text:
        requirement_id = request.requirement_id or _first_requirement_id(
            requirements,
            parsed_requirements,
            coverage_items,
        )
        return requirement_id, request.requirement_text or _joined_context_text(context), context

    for item in [*parsed_requirements, *requirements]:
        requirement_id = str(item.get("requirement_id") or "").strip()
        text = _text_from_item(item)
        if requirement_id and text:
            return requirement_id, text, context

    if coverage_items:
        requirement_id = _first_requirement_id([], [], coverage_items)
        return requirement_id, _joined_context_text({"coverage_items": coverage_items}), context

    fallback_id = requirement_ids[0] if requirement_ids else "REQ-AUT-FSM"
    fallback_text = "系统存在有状态行为，应使用有限状态机进行建模。"
    return fallback_id, fallback_text, context


def _requested_requirement_ids(request: FsmRequest) -> list[str]:
    ids = list(request.requirement_ids)
    if request.requirement_id:
        ids.append(request.requirement_id)
    for item in to_dicts(request.requirements) + to_dicts(request.parsed_requirements):
        value = str(item.get("requirement_id") or "").strip()
        if value:
            ids.append(value)
    return _dedupe(ids)


def _request_or_store_items(
    session_id: str,
    key: str,
    request_items: list[dict[str, Any]],
    requirement_ids: list[str],
) -> list[dict[str, Any]]:
    items = request_items or workflow_store.get_list(session_id, key)
    if not requirement_ids:
        return items
    selected = set(requirement_ids)
    return [
        item
        for item in items
        if str(item.get("requirement_id") or item.get("id") or "") in selected
    ]


def _first_requirement_id(*collections: list[dict[str, Any]]) -> str:
    for collection in collections:
        for item in collection:
            value = str(item.get("requirement_id") or "").strip()
            if value:
                return value
    return "REQ-AUT-FSM"


def _text_from_item(item: dict[str, Any]) -> str:
    text = extract_requirement_text(item)
    if text:
        return text
    for key in ("raw_text", "description", "goal", "expected_action"):
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _joined_context_text(context: dict[str, Any]) -> str:
    values: list[str] = []
    for value in context.values():
        values.extend(_flatten_text(value))
    return " ".join(item for item in values if item.strip())


def _flatten_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(_flatten_text(item))
        return values
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(_flatten_text(item))
        return values
    return [str(value)]


def _to_fsm_result(data: dict[str, Any]) -> FsmResult:
    model = data.get("fsm_model", {}) if isinstance(data.get("fsm_model"), dict) else {}
    states = model.get("states", []) if isinstance(model.get("states"), list) else []
    transitions = model.get("transitions", []) if isinstance(model.get("transitions"), list) else []
    state_names = {
        str(item.get("state_id")): str(item.get("name") or item.get("state_id"))
        for item in states
        if isinstance(item, dict)
    }

    transition_models = [
        FsmTransition(
            from_state=state_names.get(str(item.get("source_state")), str(item.get("source_state"))),
            to=state_names.get(str(item.get("target_state")), str(item.get("target_state"))),
            event=str(item.get("event") or ""),
            condition=str(item.get("condition") or ""),
            action=str(item.get("action") or ""),
            transition_id=item.get("transition_id"),
            source_state=item.get("source_state"),
            target_state=item.get("target_state"),
            requirement_id=item.get("requirement_id"),
            coverage_item_id=item.get("coverage_item_id"),
        )
        for item in transitions
        if isinstance(item, dict)
    ]

    return FsmResult(
        states=[
            state_names.get(str(item.get("state_id")), str(item.get("state_id")))
            for item in states
            if isinstance(item, dict)
        ],
        transitions=transition_models,
        coverage_paths=_coverage_paths(data.get("traceability", {})),
        coverage={
            "all_states": [str(item.get("state_id")) for item in states if isinstance(item, dict)],
            "all_transitions": [
                str(item.get("transition_id")) for item in transitions if isinstance(item, dict)
            ],
        },
        mermaid=str(data.get("mermaid") or model.get("mermaid") or ""),
        model_id=model.get("model_id"),
        initial_state=model.get("initial_state"),
        traceability=data.get("traceability", {}),
    )


def _coverage_paths(traceability: Any) -> list[str]:
    if not isinstance(traceability, dict):
        return []
    paths = traceability.get("paths", [])
    if not isinstance(paths, list):
        return []
    return [
        " -> ".join(str(part) for part in path)
        for path in paths
        if isinstance(path, list) and path
    ]


def _to_test_case(item: dict[str, Any]) -> TestCase:
    coverage_item_id = str(item.get("coverage_item_id") or "")
    return TestCase(
        test_id=str(item.get("test_id") or ""),
        requirement_id=str(item.get("requirement_id") or ""),
        coverage_item_id=coverage_item_id,
        strategy_id=str(item.get("strategy_id") or _strategy_id_for_fsm_case(item)),
        technique="FSM",
        title=str(item.get("title") or "FSM 状态迁移测试用例"),
        preconditions=list(item.get("preconditions") or []),
        input_data=item.get("input_data") if isinstance(item.get("input_data"), dict) else {
            "covered_states": item.get("covered_states", []),
            "covered_transitions": item.get("covered_transitions", []),
        },
        test_steps=list(item.get("test_steps") or item.get("steps") or []),
        expected_result=str(item.get("expected_result") or ""),
        standard_ref=str(item.get("standard_ref") or "ISTQB 状态迁移测试 / 有限状态机测试"),
        risk_level=str(item.get("risk_level") or "Medium"),
        status=str(item.get("status") or "Draft"),
        coverage_item_ids=item.get("coverage_item_ids", [coverage_item_id] if coverage_item_id else []),
        covered_states=item.get("covered_states", []),
        covered_transitions=item.get("covered_transitions", []),
        traceability=item.get("traceability", {}),
    )


def _strategy_id_for_fsm_case(item: dict[str, Any]) -> str:
    transitions = item.get("covered_transitions") if isinstance(item.get("covered_transitions"), list) else []
    return "STR-AUT-FSM-TRANSITIONS" if transitions else "STR-AUT-FSM-STATES"


def _to_workflow_coverage_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        coverage_item_id = str(item.get("coverage_item_id") or f"COV-AUT-FSM-{index:03d}")
        normalized.append(
            {
                **item,
                "coverage_item_id": coverage_item_id,
                "coverage_goal_id": str(item.get("coverage_goal_id") or f"CG-AUT-FSM-{index:03d}"),
                "requirement_id": str(item.get("requirement_id") or "REQ-AUT-FSM"),
                "technique": "FSM",
                "conditions": item.get("covered_transitions", []),
                "data_ranges": [],
                "input_fields": item.get("covered_states", []),
                "expected_action": item.get("description", "执行 FSM 覆盖项。"),
                "strategy_rationale": str(item.get("strategy") or "FSM 覆盖策略"),
                "technique_reason": "具有状态相关行为，适合使用 FSM 状态迁移测试覆盖。",
                "status": "ai_generated",
            }
        )
    return normalized


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
