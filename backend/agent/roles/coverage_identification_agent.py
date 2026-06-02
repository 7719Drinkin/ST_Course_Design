from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import AnalyzedRequirement, CoverageGoal
from ..tools.validation.id_gate import CG_ID_RE, require_id_format, require_unique_ids
from ..tools.validation.output_validator import validate_coverage_goals


MAX_ID_REPAIR_ATTEMPTS = 2


class CoverageIdentificationAgent(BaseAgent):
    """Identify business coverage goals without assigning test techniques."""

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            if not context.analyzed_requirements:
                raise ValueError("analyzed_requirements are required.")
            if not context.risk_analysis:
                raise ValueError("risk_analysis are required.")

            quality_feedback = ""
            coverage_goals: list[CoverageGoal] = []
            for attempt in range(MAX_ID_REPAIR_ATTEMPTS + 1):
                coverage_goals = await self._run_validated_json_prompt(
                    "coverage_identification",
                    {
                        "analyzed_requirements": context.analyzed_requirements,
                        "risk_analysis": context.risk_analysis,
                        "quality_feedback": quality_feedback,
                    },
                    context,
                    "coverage_goals",
                    validate_coverage_goals,
                )
                try:
                    self._validate_coverage_goals(
                        coverage_goals,
                        context.analyzed_requirements,
                    )
                    break
                except ValueError as exc:
                    if attempt >= MAX_ID_REPAIR_ATTEMPTS:
                        raise
                    quality_feedback = str(exc)

            context.coverage_goals = coverage_goals
            return AgentResult(success=True, data={"coverage_goals": context.coverage_goals})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    def _validate_coverage_goals(
        self,
        coverage_goals: list[CoverageGoal],
        analyzed_requirements: list[AnalyzedRequirement],
    ) -> None:
        require_id_format(coverage_goals, "coverage_goal_id", CG_ID_RE, "coverage_goals")
        require_unique_ids(coverage_goals, "coverage_goal_id", "coverage_goals")
        requirement_ids = {item.requirement_id for item in analyzed_requirements}
        for index, goal in enumerate(coverage_goals):
            if goal.requirement_id not in requirement_ids:
                raise ValueError(
                    f"coverage_goals[{index}].requirement_id is unknown: {goal.requirement_id}"
                )
            expected_prefix = goal.requirement_id.replace("REQ-AUT-", "CG-AUT-", 1)
            if not goal.coverage_goal_id.startswith(f"{expected_prefix}-"):
                raise ValueError(
                    f"coverage_goals[{index}].coverage_goal_id must align with requirement_id: "
                    f"{goal.coverage_goal_id} does not start with {expected_prefix}-"
                )
