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
            specs = workflow_store.get_list(request.session_id, "test_design_specs")
            return GenerateResponse(test_design_specs=specs, test_cases=stored, prompts_used=[])
        return GenerateResponse(test_design_specs=[], test_cases=[], prompts_used=[])

    async def fsm(self, request: FsmRequest) -> FsmResponse:
        stored_fsm = workflow_store.get_object(request.session_id, "fsm")
        if stored_fsm and isinstance(stored_fsm, dict) and stored_fsm:
            stored_cases = workflow_store.get_list(request.session_id, "fsm_test_cases")
            return FsmResponse(
                session_id=request.session_id,
                fsm=stored_fsm,
                test_cases=stored_cases,
                prompt_evidence=[],
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
            return OracleResponse(
                session_id=request.session_id,
                oracle_results=stored,
                prompt_evidence=[],
            )
        return OracleResponse(
            session_id=request.session_id,
            oracle_results=[],
            prompt_evidence=[],
        )
