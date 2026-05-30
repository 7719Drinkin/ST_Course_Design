"""Step 4 business logic: test generation, FSM, Oracle — store-first read, no inline pipeline."""

from __future__ import annotations

from ..store import workflow_store
from .schemas import (
    FsmRequest,
    FsmResponse,
    FsmResult,
    GenerateRequest,
    GenerateResponse,
    OracleRequest,
    OracleResponse,
)


class TestDesignService:

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        stored = workflow_store.get_list(request.session_id, "test_cases")
        if stored:
            # Filter: only FR3 cases (technique != FSM, has test_id)
            valid = [c for c in stored if c.get("test_id") and c.get("technique") and c.get("technique") != "FSM"]
            specs = workflow_store.get_list(request.session_id, "test_design_specs")
            evidence = workflow_store.get_list(request.session_id, "prompt_evidence")
            return GenerateResponse(test_design_specs=specs, test_cases=valid, prompts_used=evidence)
        return GenerateResponse(test_design_specs=[], test_cases=[], prompts_used=[])

    async def fsm(self, request: FsmRequest) -> FsmResponse:
        stored_fsm = workflow_store.get_object(request.session_id, "fsm")
        if stored_fsm and isinstance(stored_fsm, dict) and stored_fsm:
            stored_cases = workflow_store.get_list(request.session_id, "fsm_test_cases")
            evidence = workflow_store.get_list(request.session_id, "prompt_evidence")
            return FsmResponse(
                session_id=request.session_id,
                fsm=stored_fsm,
                test_cases=stored_cases,
                prompt_evidence=evidence,
            )
        return FsmResponse(
            session_id=request.session_id,
            fsm=FsmResult(),
            test_cases=[],
            prompt_evidence=[],
        )

    async def oracle(self, request: OracleRequest) -> OracleResponse:
        stored = workflow_store.get_list(request.session_id, "oracle_results")
        if stored:
            evidence = workflow_store.get_list(request.session_id, "prompt_evidence")
            return OracleResponse(
                session_id=request.session_id,
                oracle_results=stored,
                prompt_evidence=evidence,
            )
        return OracleResponse(
            session_id=request.session_id,
            oracle_results=[],
            prompt_evidence=[],
        )
