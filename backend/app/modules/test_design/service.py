"""Step 4 业务逻辑：测试设计、FSM 状态迁移与 Oracle 审查。"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..util import (
    STAGE_FSM,
    STAGE_GENERATE,
    STAGE_ORACLE,
    effective_rag_context,
    evidence,
    next_index,
    normalize_stage_output,
    parse_sse_event,
    prompt_records_to_evidence,
    resolve_requirement_text,
    save_requirement_input,
    stage_output_summary,
    to_dicts,
)
from ..store import workflow_store
from .schemas import (
    FsmRequest,
    FsmResponse,
    FsmResult,
    GenerateRequest,
    GenerateResponse,
    OracleRequest,
    OracleResult,
    OracleResponse,
)

from agent import generate_blackbox_tests_stream
from agent.tools.fsm import generate_fsm_tests


class TestDesignService:
    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        requirement_text = resolve_requirement_text(
            session_id=request.session_id,
            explicit_text=request.requirement_text,
            fallback_payload={
                "coverage_items": request.coverage_items,
                "risk_analysis": request.risk_analysis or [],
            },
        )
        save_requirement_input(request.session_id, requirement_text, request.rag_context)
        output, _ = await _runner_stage_output(
            request.session_id,
            requirement_text,
            request.rag_context,
            STAGE_GENERATE,
        )
        return GenerateResponse(
            test_design_specs=output.get("test_design_specs", []),
            test_cases=output.get("test_cases", []),
            prompts_used=output.get("prompts_used", []),
        )

    async def fsm(self, request: FsmRequest) -> FsmResponse:
        requirement_text = resolve_requirement_text(
            session_id=request.session_id,
            explicit_text=request.requirement_text,
            fallback_payload={
                "requirements": request.requirements,
                "parsed_requirements": request.parsed_requirements,
                "coverage_items": request.coverage_items,
                "state_candidates": request.state_candidates or [],
            },
        )
        try:
            output, prompt_evidence = await _runner_stage_output(
                request.session_id,
                requirement_text,
                request.rag_context,
                STAGE_FSM,
            )
            return FsmResponse(
                session_id=request.session_id,
                fsm=output.get("fsm") or {},
                test_cases=output.get("test_cases", []),
                prompt_evidence=prompt_evidence,
            )
        except HTTPException as exc:
            if exc.status_code < 500 and requirement_text:
                raise
            return self._deterministic_fsm_fallback(request, requirement_text, exc)

    async def oracle(self, request: OracleRequest) -> OracleResponse:
        test_cases = _oracle_test_cases(request)
        requirements = _oracle_requirements(request, test_cases)
        source_context_ids = request.source_context_ids or []

        try:
            requirement_text = resolve_requirement_text(
                session_id=request.session_id,
                explicit_text=request.requirement_text,
                fallback_payload={
                    "requirements": requirements,
                    "test_cases": test_cases,
                },
            )
            output, prompt_evidence = await _runner_stage_output(
                request.session_id,
                requirement_text,
                request.rag_context or _joined_context_text({"requirements": requirements}),
                STAGE_ORACLE,
            )
            oracle_results = [
                _to_oracle_result(item)
                for item in output.get("oracle_results", [])
            ]
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

    def _deterministic_fsm_fallback(
        self,
        request: FsmRequest,
        requirement_text: str,
        failure: Exception,
    ) -> FsmResponse:
        requirement_id = _fsm_requirement_id(request)
        result = generate_fsm_tests(
            requirement_id=requirement_id,
            requirement_text=requirement_text or requirement_id,
            context={
                "requirements": to_dicts(request.requirements),
                "parsed_requirements": to_dicts(request.parsed_requirements),
                "coverage_items": to_dicts(request.coverage_items),
                "state_candidates": request.state_candidates or [],
            },
            strategies=request.strategies,
            max_depth=request.max_depth,
        )
        data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
        fsm = _deterministic_fsm_result(data)
        test_cases = data.get("test_cases", []) if isinstance(data.get("test_cases"), list) else []
        prompt_evidence = [
            evidence(
                request.session_id,
                "fsm_generation_fallback",
                requirement_id,
                {
                    "requirement_id": requirement_id,
                    "state_candidates": request.state_candidates or [],
                    "runner_error": str(failure),
                },
                stage_output_summary(
                    STAGE_FSM,
                    {"fsm": fsm.model_dump(mode="json", by_alias=True), "test_cases": test_cases},
                ),
                next_index(
                    workflow_store.get_list(request.session_id, "prompt_evidence"),
                    "evidence_id",
                    "PE-AUT",
                ),
                "Agent runner FSM stage failed; deterministic FSM generator was used as a fallback.",
            )
        ]

        save_requirement_input(request.session_id, requirement_text, request.rag_context)
        workflow_store.save_object(request.session_id, "fsm", fsm)
        workflow_store.save_many(request.session_id, "test_cases", test_cases, "test_id")
        workflow_store.save_many(request.session_id, "prompt_evidence", prompt_evidence, "evidence_id")

        return FsmResponse(
            session_id=request.session_id,
            fsm=fsm,
            test_cases=test_cases,
            prompt_evidence=prompt_evidence,
        )


async def _runner_stage_output(
    session_id: str,
    requirement_text: str,
    rag_context: str | None,
    target_stage: str,
) -> tuple[dict, list[Any]]:
    stream = generate_blackbox_tests_stream(
        requirement_text=requirement_text,
        rag_context=effective_rag_context(session_id, rag_context),
    )
    try:
        async for raw_event in stream:
            event, data = parse_sse_event(raw_event)
            if event == "stage" and data.get("stage") == target_stage:
                output = normalize_stage_output(data.get("output") or {})
                prompt_evidence = _save_stage_output(session_id, target_stage, output)
                return output, prompt_evidence
            if event == "stage_error":
                _raise_stage_error(data)
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            await aclose()
    raise HTTPException(status_code=502, detail=f"Runner did not emit {target_stage} stage")


def _save_stage_output(session_id: str, stage: str, output: dict) -> list[Any]:
    if stage == STAGE_GENERATE:
        workflow_store.save_many(
            session_id,
            "test_design_specs",
            output.get("test_design_specs", []),
            "spec_id",
            replace_all=True,
        )
        workflow_store.save_many(session_id, "test_cases", output.get("test_cases", []), "test_id")
        target_id = "test_cases"
    elif stage == STAGE_FSM:
        workflow_store.save_object(session_id, "fsm", output.get("fsm") or {})
        workflow_store.save_many(session_id, "test_cases", output.get("test_cases", []), "test_id")
        target_id = "fsm"
    elif stage == STAGE_ORACLE:
        workflow_store.save_many(
            session_id,
            "oracle_results",
            output.get("oracle_results", []),
            "test_id",
            replace_all=True,
        )
        target_id = "oracle_results"
    else:
        target_id = stage

    prompt_evidence = prompt_records_to_evidence(
        session_id=session_id,
        records=output.get("prompts_used"),
        target_id=target_id,
        output_data=stage_output_summary(stage, output),
        note=f"Agent runner stage {stage} prompt evidence.",
    )
    workflow_store.save_many(session_id, "prompt_evidence", prompt_evidence, "evidence_id")
    return prompt_evidence


def _raise_stage_error(data: dict) -> None:
    status = 400 if data.get("stage") == "input_validation" else 502
    raise HTTPException(status_code=status, detail=data.get("error") or "Agent runner stage failed")


def _oracle_test_cases(request: OracleRequest) -> list[dict[str, Any]]:
    return to_dicts(request.test_cases)


def _fsm_requirement_id(request: FsmRequest) -> str:
    if request.requirement_id:
        return request.requirement_id
    if request.requirement_ids:
        return request.requirement_ids[0]
    for collection in (request.requirements or [], request.parsed_requirements or []):
        payload = collection.model_dump(mode="json", by_alias=True) if hasattr(collection, "model_dump") else collection
        if isinstance(payload, dict) and payload.get("requirement_id"):
            return str(payload["requirement_id"])
    return "REQ-AUT-FSM"


def _deterministic_fsm_result(data: dict[str, Any]) -> FsmResult:
    model = data.get("fsm_model") if isinstance(data.get("fsm_model"), dict) else {}
    state_items = model.get("states") if isinstance(model.get("states"), list) else []
    transition_items = model.get("transitions") if isinstance(model.get("transitions"), list) else []
    state_names = {
        str(item.get("state_id") or ""): str(item.get("name") or item.get("state_id") or "")
        for item in state_items
        if isinstance(item, dict)
    }
    states = [name for name in state_names.values() if name]
    transitions = []
    for item in transition_items:
        if not isinstance(item, dict):
            continue
        transitions.append(
            {
                "from": state_names.get(str(item.get("source_state") or ""), str(item.get("source_state") or "")),
                "to": state_names.get(str(item.get("target_state") or ""), str(item.get("target_state") or "")),
                "event": str(item.get("event") or ""),
                "condition": str(item.get("condition") or ""),
                "action": str(item.get("action") or ""),
            }
        )
    coverage_paths = _deterministic_coverage_paths(data, state_names)
    return FsmResult(
        states=states,
        transitions=transitions,
        coverage_paths=coverage_paths,
        coverage={
            "all_states": states,
            "all_transitions": [str(item.get("transition_id") or "") for item in transition_items if isinstance(item, dict)],
        },
        mermaid=str(data.get("mermaid") or model.get("mermaid") or ""),
    )


def _deterministic_coverage_paths(
    data: dict[str, Any],
    state_names: dict[str, str],
) -> list[str]:
    test_cases = data.get("test_cases") if isinstance(data.get("test_cases"), list) else []
    paths: list[str] = []
    for item in test_cases:
        if not isinstance(item, dict):
            continue
        covered_states = item.get("covered_states") if isinstance(item.get("covered_states"), list) else []
        path = " -> ".join(state_names.get(str(state), str(state)) for state in covered_states if state)
        if path:
            paths.append(path)
    if paths:
        return paths
    return [" -> ".join(state_names.values())] if state_names else []


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
            f"oracle_generation prompt 执行失败，已使用确定性 Oracle 兜底：{failure}",
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
        explanation = "根据 requirement_id 匹配到的需求依据生成建议结果。"
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
        return f'执行“{title}”后，请人工复核 expected_result 是否与需求一致。'
    if steps:
        return "执行测试步骤后，请人工复核可观察结果是否与需求一致。"
    return "请人工复核系统可观察结果是否与需求一致。"


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


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
