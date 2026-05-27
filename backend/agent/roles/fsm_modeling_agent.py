from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..tools.validation.output_validator import validate_fsm_generation


class FsmModelingAgent(BaseAgent):
    """Generate FR4 FSM model and FSM test cases from state-related inputs."""

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            if not (
                context.fsm_requirements
                or context.fsm_parsed_requirements
                or context.fsm_coverage_items
            ):
                raise ValueError("FSM requirements, parsed requirements, or coverage items are required.")

            payload = await self._run_json_prompt(
                "fsm_modeling",
                {
                    "requirements": context.fsm_requirements,
                    "parsed_requirements": context.fsm_parsed_requirements,
                    "coverage_items": context.fsm_coverage_items,
                    "state_candidates": context.state_candidates,
                    "rag_context": context.rag_context or "",
                },
                context,
            )
            result = validate_fsm_generation(payload)
            context.fsm = result.fsm
            context.fsm_test_cases = result.test_cases
            return AgentResult(
                success=True,
                data={
                    "fsm": result.fsm,
                    "test_cases": result.test_cases,
                },
            )
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))
