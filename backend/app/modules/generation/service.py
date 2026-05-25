from __future__ import annotations

from typing import Any
import json

from .schemas import GenerateMetadata, GenerateRequest, GenerateResponse

try:  # Supports tests importing from project root.
    import backend.agent as agent_module
    from backend.agent.tools.blackbox_algorithms import generate_deterministic_blackbox_tests
    from backend.agent.tools.blackbox_algorithms.models import standard_ref_for
    from backend.agent.tools.fsm import generate_fsm_tests
except ModuleNotFoundError:  # Supports uvicorn launched from backend/.
    import agent as agent_module
    from agent.tools.blackbox_algorithms import generate_deterministic_blackbox_tests
    from agent.tools.blackbox_algorithms.models import standard_ref_for
    from agent.tools.fsm import generate_fsm_tests


DATA_KEYS = ("coverage_items", "test_design_specs", "test_cases")
ALLOWED_TECHNIQUES = {"EP", "BVA", "DT", "FSM"}
BLACKBOX_TECHNIQUES = {"EP", "BVA", "DT"}


class GenerationService:
    async def generate_test_cases(self, request: GenerateRequest) -> GenerateResponse:
        mode = request.generation_mode

        if mode == "deterministic":
            deterministic = self._run_deterministic(request)
            return self._response(
                success=deterministic["success"],
                data=deterministic["data"],
                request=request,
                agent_used=False,
                deterministic_used=True,
                fallback_used=False,
                fallback_reason=None,
                errors=deterministic["errors"],
            )

        if mode == "agent":
            agent_data, reason, errors = await self._run_agent_and_normalize(request)
            if agent_data is None:
                return self._response(
                    success=False,
                    data=_empty_data(),
                    request=request,
                    agent_used=True,
                    deterministic_used=False,
                    fallback_used=False,
                    fallback_reason=reason,
                    errors=errors,
                )
            return self._response(
                success=True,
                data=agent_data,
                request=request,
                agent_used=True,
                deterministic_used=False,
                fallback_used=False,
                fallback_reason=None,
                errors=[],
            )

        if mode == "hybrid":
            agent_data, reason, errors = await self._run_agent_and_normalize(request)
            deterministic = self._run_deterministic(request)
            merged_data = (
                self._merge_data(agent_data, deterministic["data"])
                if agent_data is not None
                else deterministic["data"]
            )
            return self._response(
                success=agent_data is not None or deterministic["success"],
                data=merged_data,
                request=request,
                agent_used=True,
                deterministic_used=True,
                fallback_used=agent_data is None,
                fallback_reason=reason if agent_data is None else None,
                errors=(errors if agent_data is None else []) + deterministic["errors"],
            )

        agent_data, reason, errors = await self._run_agent_and_normalize(request)
        if agent_data is not None:
            fsm_added = False
            if _requires_fsm(request) and not _data_has_technique(agent_data, "FSM"):
                fsm_result = self._run_fsm(request)
                agent_data = self._merge_data(agent_data, fsm_result["data"])
                errors.extend(fsm_result["errors"])
                fsm_added = bool(fsm_result["success"])
            return self._response(
                success=fsm_added or not errors,
                data=agent_data,
                request=request,
                agent_used=True,
                deterministic_used=fsm_added,
                fallback_used=False,
                fallback_reason=None,
                errors=errors,
            )

        deterministic = self._run_deterministic(request)
        return self._response(
            success=deterministic["success"],
            data=deterministic["data"],
            request=request,
            agent_used=True,
            deterministic_used=True,
            fallback_used=True,
            fallback_reason=reason,
            errors=errors + deterministic["errors"],
        )

    async def _run_agent_and_normalize(
        self,
        request: GenerateRequest,
    ) -> tuple[dict[str, list[dict[str, Any]]] | None, str | None, list[str]]:
        try:
            raw = await agent_module.generate_blackbox_tests(
                request.requirement_text,
                rag_context=self._rag_context(request),
            )
        except Exception as exc:
            return None, "agent_exception", [str(exc)]

        if raw.get("success") is False:
            message = str(raw.get("error") or "Agent returned success=false.")
            return None, "invalid_agent_result", [message]

        try:
            return self._normalize_agent_result(raw, request), None, []
        except ValueError as exc:
            reason = "empty_test_cases" if "empty test_cases" in str(exc) else "invalid_agent_result"
            return None, reason, [str(exc)]

    def _run_deterministic(self, request: GenerateRequest) -> dict[str, Any]:
        data = _empty_data()
        errors: list[str] = []
        success = True
        blackbox_techniques = _blackbox_techniques(request)

        if blackbox_techniques:
            blackbox_result = self._run_blackbox_deterministic(request, blackbox_techniques)
            data = self._merge_data(data, blackbox_result["data"])
            errors.extend(blackbox_result["errors"])
            success = success and bool(blackbox_result["success"])

        if _requires_fsm(request):
            fsm_result = self._run_fsm(request)
            data = self._merge_data(data, fsm_result["data"])
            errors.extend(fsm_result["errors"])
            success = success and bool(fsm_result["success"])

        data.setdefault("metadata", {})["deterministic"] = {
            "techniques": request.techniques,
            "blackbox_techniques": blackbox_techniques,
            "fsm_used": _requires_fsm(request),
            "case_count": len(data.get("test_cases", [])),
        }
        return {
            "success": success,
            "data": data,
            "metadata": {
                "deterministic": True,
                "techniques": request.techniques,
                "case_count": len(data.get("test_cases", [])),
            },
            "errors": errors,
        }

    def _run_blackbox_deterministic(
        self,
        request: GenerateRequest,
        techniques: list[str],
    ) -> dict[str, Any]:
        try:
            return generate_deterministic_blackbox_tests(
                requirement_id=request.requirement_id,
                requirement_text=request.requirement_text,
                techniques=techniques,
                context=request.context,
            )
        except Exception as exc:
            return {
                "success": False,
                "data": _empty_data(),
                "metadata": {
                    "deterministic": True,
                    "techniques": request.techniques,
                    "case_count": 0,
                },
                "errors": [str(exc)],
            }

    def _run_fsm(self, request: GenerateRequest) -> dict[str, Any]:
        try:
            result = generate_fsm_tests(
                requirement_id=request.requirement_id,
                requirement_text=request.requirement_text,
                context=request.context,
                strategies=_fsm_strategies(request),
                max_depth=_fsm_max_depth(request),
            )
            data = result.get("data", {}) if isinstance(result.get("data"), dict) else _empty_data()
            data.setdefault("metadata", {})["fsm"] = result.get("metadata", {})
            return {
                "success": bool(result.get("success", True)),
                "data": data,
                "metadata": result.get("metadata", {}),
                "errors": result.get("errors", []),
            }
        except Exception as exc:
            return {
                "success": False,
                "data": _empty_data(),
                "metadata": {"techniques": ["FSM"], "case_count": 0},
                "errors": [str(exc)],
            }

    def _normalize_agent_result(
        self,
        raw: dict[str, Any],
        request: GenerateRequest,
    ) -> dict[str, list[dict[str, Any]]]:
        raw_data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        raw_cases = raw_data.get("test_cases", []) if isinstance(raw_data, dict) else []
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError("empty test_cases from Agent")

        requested = set(request.techniques)
        coverage_items = _normalize_coverage_items(raw_data.get("coverage_items", []), request)
        coverage_by_id = {
            item["coverage_item_id"]: item
            for item in coverage_items
            if item.get("coverage_item_id")
        }

        normalized_cases: list[dict[str, Any]] = []
        for index, item in enumerate(raw_cases, start=1):
            if not isinstance(item, dict):
                raise ValueError("Agent test_cases must be dict items.")

            case = dict(item)
            technique = _normalize_case_technique(case.get("technique"), request.techniques)
            if technique not in requested:
                raise ValueError(f"Agent returned technique outside request: {technique}")

            expected_result = str(case.get("expected_result", "")).strip()
            if not expected_result:
                raise ValueError("Agent test_case missing expected_result.")

            requirement_id = str(case.get("requirement_id") or request.requirement_id)
            coverage_item_id = str(
                case.get("coverage_item_id")
                or _coverage_id_for_case(coverage_items, requirement_id, technique)
                or f"COV-AGT-{_safe_id(requirement_id)}-{technique}-{index:03d}"
            )
            case = {
                "test_id": str(case.get("test_id") or f"TC-AGT-{_safe_id(requirement_id)}-{technique}-{index:03d}"),
                "requirement_id": requirement_id,
                "coverage_item_id": coverage_item_id,
                "spec_id": str(case.get("spec_id") or f"SPEC-AGT-{_safe_id(requirement_id)}-{technique}-{index:03d}"),
                "technique": technique,
                "title": str(case.get("title") or f"{technique} Agent generated test case {index}"),
                "preconditions": _as_list(case.get("preconditions")),
                "input_data": case.get("input_data") if isinstance(case.get("input_data"), dict) else {},
                "test_steps": _as_list(case.get("test_steps")) or ["Execute the generated black-box test case."],
                "expected_result": expected_result,
                "risk_level": case.get("risk_level", _risk_level(request)),
                "standard_ref": str(case.get("standard_ref") or _standard_ref_for(technique)),
                "status": str(case.get("status") or "Draft"),
            }
            if case["status"] != "Draft":
                case["status"] = "Draft"
            normalized_cases.append(case)

            if coverage_item_id not in coverage_by_id:
                coverage_by_id[coverage_item_id] = _synthetic_coverage_item(
                    coverage_item_id,
                    requirement_id,
                    technique,
                    request,
                )

        coverage_items = list(coverage_by_id.values())
        return {
            "coverage_items": coverage_items,
            "test_design_specs": _normalize_design_specs(
                raw_data.get("test_design_specs", []),
                coverage_items,
                normalized_cases,
            ),
            "test_cases": normalized_cases,
        }

    def _merge_data(
        self,
        agent_data: dict[str, Any] | None,
        deterministic_data: dict[str, Any],
    ) -> dict[str, Any]:
        if agent_data is None:
            return deterministic_data
        merged = {
            "coverage_items": _dedupe_by_key(
                agent_data.get("coverage_items", []) + deterministic_data.get("coverage_items", []),
                "coverage_item_id",
            ),
            "test_design_specs": _dedupe_by_key(
                agent_data.get("test_design_specs", []) + deterministic_data.get("test_design_specs", []),
                "spec_id",
            ),
            "test_cases": _dedupe_cases(
                agent_data.get("test_cases", []) + deterministic_data.get("test_cases", [])
            ),
        }
        for key in sorted(set(agent_data) | set(deterministic_data)):
            if key in DATA_KEYS:
                continue
            deterministic_value = deterministic_data.get(key)
            agent_value = agent_data.get(key)
            if key == "metadata":
                merged[key] = _merge_metadata(agent_value, deterministic_value)
            else:
                merged[key] = deterministic_value if deterministic_value not in (None, {}, []) else agent_value
        return merged

    def _response(
        self,
        success: bool,
        data: dict[str, Any],
        request: GenerateRequest,
        agent_used: bool,
        deterministic_used: bool,
        fallback_used: bool,
        fallback_reason: str | None,
        errors: list[str],
    ) -> GenerateResponse:
        normalized_data = _ensure_data(data)
        return GenerateResponse(
            success=success,
            data=normalized_data,
            metadata=GenerateMetadata(
                generation_mode=request.generation_mode,
                agent_used=agent_used,
                deterministic_used=deterministic_used,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                techniques=request.techniques,
                case_count=len(normalized_data["test_cases"]),
            ),
            errors=errors,
        )

    def _rag_context(self, request: GenerateRequest) -> str | None:
        explicit_context = request.context.get("rag_context")
        if explicit_context:
            return str(explicit_context)
        if request.use_rag:
            return None
        return "RAG disabled by /generate request."


def _normalize_coverage_items(items: Any, request: GenerateRequest) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        technique = _normalize_case_technique(item.get("technique"), request.techniques)
        if technique not in set(request.techniques):
            continue
        requirement_id = str(item.get("requirement_id") or request.requirement_id)
        coverage_item_id = str(
            item.get("coverage_item_id")
            or item.get("id")
            or f"COV-AGT-{_safe_id(requirement_id)}-{technique}-{index:03d}"
        )
        normalized.append(
            {
                "coverage_item_id": coverage_item_id,
                "coverage_goal_id": str(
                    item.get("coverage_goal_id")
                    or f"GOAL-AGT-{_safe_id(requirement_id)}-{technique}"
                ),
                "requirement_id": requirement_id,
                "technique": technique,
                "description": str(item.get("description") or f"Agent coverage for {requirement_id}"),
                "conditions": _as_list(item.get("conditions")),
                "data_ranges": item.get("data_ranges") if isinstance(item.get("data_ranges"), list) else [],
                "input_fields": _as_list(item.get("input_fields")),
                "expected_action": str(item.get("expected_action") or "Verify expected requirement behavior."),
                "strategy_rationale": str(
                    item.get("strategy_rationale")
                    or "Agent-selected black-box coverage item."
                ),
                "standard_ref": str(item.get("standard_ref") or _standard_ref_for(technique)),
            }
        )
    return normalized


def _normalize_design_specs(
    items: Any,
    coverage_items: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            technique = str(item.get("technique", "")).upper()
            if technique not in ALLOWED_TECHNIQUES:
                continue
            coverage_item_id = str(item.get("coverage_item_id") or "")
            related = [case for case in test_cases if case["coverage_item_id"] == coverage_item_id]
            if not related:
                continue
            normalized.append(
                {
                    "spec_id": str(item.get("spec_id") or related[0]["spec_id"]),
                    "coverage_item_id": coverage_item_id,
                    "requirement_id": str(item.get("requirement_id") or related[0]["requirement_id"]),
                    "technique": technique,
                    "design_points": item.get("design_points") if isinstance(item.get("design_points"), list) and item.get("design_points") else _design_points(related),
                    "standard_ref": str(item.get("standard_ref") or _standard_ref_for(technique)),
                }
            )

    seen = {item["coverage_item_id"] for item in normalized}
    for coverage_item in coverage_items:
        coverage_item_id = coverage_item["coverage_item_id"]
        if coverage_item_id in seen:
            continue
        related = [case for case in test_cases if case["coverage_item_id"] == coverage_item_id]
        if not related:
            continue
        normalized.append(
            {
                "spec_id": related[0]["spec_id"],
                "coverage_item_id": coverage_item_id,
                "requirement_id": coverage_item["requirement_id"],
                "technique": coverage_item["technique"],
                "design_points": _design_points(related),
                "standard_ref": _standard_ref_for(coverage_item["technique"]),
            }
        )
    return normalized


def _design_points(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "test_id": case["test_id"],
            "title": case["title"],
            "input_data": case["input_data"],
            "expected_result": case["expected_result"],
        }
        for case in cases
    ]


def _coverage_id_for_case(
    coverage_items: list[dict[str, Any]],
    requirement_id: str,
    technique: str,
) -> str:
    matches = [
        item["coverage_item_id"]
        for item in coverage_items
        if item.get("requirement_id") == requirement_id and item.get("technique") == technique
    ]
    return matches[0] if len(matches) == 1 else ""


def _synthetic_coverage_item(
    coverage_item_id: str,
    requirement_id: str,
    technique: str,
    request: GenerateRequest,
) -> dict[str, Any]:
    return {
        "coverage_item_id": coverage_item_id,
        "coverage_goal_id": f"GOAL-AGT-{_safe_id(requirement_id)}-{technique}",
        "requirement_id": requirement_id,
        "technique": technique,
        "description": f"Normalized Agent coverage for {requirement_id}",
        "conditions": _as_list(request.context.get("conditions")),
        "data_ranges": request.context.get("data_ranges") if isinstance(request.context.get("data_ranges"), list) else [],
        "input_fields": _as_list(request.context.get("input_fields")),
        "expected_action": str(request.context.get("expected_action") or "Verify expected requirement behavior."),
        "strategy_rationale": "Synthetic coverage item created to preserve test case traceability.",
        "standard_ref": _standard_ref_for(technique),
    }


def _normalize_case_technique(value: Any, requested_techniques: list[str]) -> str:
    technique = str(value or "").strip().upper()
    if not technique and len(requested_techniques) == 1:
        technique = requested_techniques[0]
    aliases = {
        "EQUIVALENCE PARTITIONING": "EP",
        "BOUNDARY VALUE ANALYSIS": "BVA",
        "DECISION TABLE": "DT",
        "FINITE STATE MACHINE": "FSM",
        "STATE TRANSITION": "FSM",
    }
    technique = aliases.get(technique, technique)
    if technique not in ALLOWED_TECHNIQUES:
        raise ValueError(f"Invalid or missing technique: {value}")
    return technique


def _risk_level(request: GenerateRequest) -> int:
    risk_scores = request.context.get("risk_scores")
    if isinstance(risk_scores, dict) and request.requirement_id in risk_scores:
        try:
            return int(risk_scores[request.requirement_id])
        except (TypeError, ValueError):
            return 3
    try:
        return int(request.context.get("risk_level", 3))
    except (TypeError, ValueError):
        return 3


def _dedupe_by_key(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        value = str(item.get(key, ""))
        if value and value not in seen:
            seen.add(value)
            result.append(item)
    return result


def _dedupe_cases(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = json.dumps(
            {
                "requirement_id": item.get("requirement_id"),
                "coverage_item_id": item.get("coverage_item_id"),
                "technique": item.get("technique"),
                "title": item.get("title"),
                "input_data": item.get("input_data"),
                "expected_result": item.get("expected_result"),
            },
            sort_keys=True,
            default=str,
        )
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _empty_data() -> dict[str, Any]:
    return {"coverage_items": [], "test_design_specs": [], "test_cases": [], "metadata": {}}


def _ensure_data(data: dict[str, Any] | None) -> dict[str, Any]:
    source = data or {}
    normalized: dict[str, Any] = {
        key: source.get(key, []) if isinstance(source.get(key, []), list) else []
        for key in DATA_KEYS
    }
    normalized["metadata"] = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    for key, value in source.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in str(value)).strip("-").upper() or "REQ"


def _blackbox_techniques(request: GenerateRequest) -> list[str]:
    return [technique for technique in request.techniques if technique in BLACKBOX_TECHNIQUES]


def _requires_fsm(request: GenerateRequest) -> bool:
    return "FSM" in request.techniques


def _data_has_technique(data: dict[str, Any], technique: str) -> bool:
    return any(
        isinstance(item, dict) and item.get("technique") == technique
        for item in data.get("test_cases", [])
    )


def _fsm_strategies(request: GenerateRequest) -> list[str] | None:
    strategies = request.context.get("fsm_strategies")
    if strategies is None:
        return None
    if isinstance(strategies, str):
        return [strategies]
    if isinstance(strategies, list):
        return [str(item) for item in strategies]
    return None


def _fsm_max_depth(request: GenerateRequest) -> int:
    try:
        return int(request.context.get("fsm_max_depth", 6))
    except (TypeError, ValueError):
        return 6


def _merge_metadata(agent_value: Any, deterministic_value: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if isinstance(agent_value, dict):
        merged.update(agent_value)
    if isinstance(deterministic_value, dict):
        merged.update(deterministic_value)
    return merged


def _standard_ref_for(technique: str) -> str:
    if technique == "FSM":
        return "ISTQB state transition testing / finite state machine testing"
    return standard_ref_for(technique)


async def generate_test_cases(request: GenerateRequest) -> GenerateResponse:
    return await GenerationService().generate_test_cases(request)
