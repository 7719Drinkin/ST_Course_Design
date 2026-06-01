from __future__ import annotations

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import CoverageGoal, CoverageItem
from ..tools.validation.id_gate import (
    COV_ID_RE,
    require_id_format,
    require_no_bad_coverage_ids,
    require_unique_ids,
)
from ..tools.validation.output_validator import validate_coverage_items


MAX_ID_REPAIR_ATTEMPTS = 2


class TechniqueAssignmentAgent(BaseAgent):
    """Assign EP/BVA/DT techniques and let the LLM maintain coverage item IDs."""

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            if not context.coverage_goals:
                raise ValueError("coverage_goals are required.")
            if not context.analyzed_requirements:
                raise ValueError("analyzed_requirements are required.")
            if not context.risk_analysis:
                raise ValueError("risk_analysis are required.")

            quality_feedback = ""
            coverage_items: list[CoverageItem] = []
            for attempt in range(MAX_ID_REPAIR_ATTEMPTS + 1):
                coverage_items = await self._run_validated_json_prompt(
                    "technique_assignment",
                    {
                        "coverage_goals": context.coverage_goals,
                        "analyzed_requirements": context.analyzed_requirements,
                        "risk_analysis": context.risk_analysis,
                        "quality_feedback": quality_feedback,
                    },
                    context,
                    "coverage_items",
                    validate_coverage_items,
                )
                try:
                    self._validate_coverage_items(coverage_items, context.coverage_goals)
                    break
                except ValueError as exc:
                    if attempt >= MAX_ID_REPAIR_ATTEMPTS:
                        raise
                    quality_feedback = str(exc)

            context.coverage_items = coverage_items
            return AgentResult(success=True, data={"coverage_items": context.coverage_items})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    def _validate_coverage_items(
        self,
        coverage_items: list[CoverageItem],
        coverage_goals: list[CoverageGoal],
    ) -> None:
        goals_by_id = {item.coverage_goal_id: item for item in coverage_goals}
        require_id_format(coverage_items, "coverage_item_id", COV_ID_RE, "coverage_items")
        require_no_bad_coverage_ids(coverage_items, "coverage_items")
        require_unique_ids(coverage_items, "coverage_item_id", "coverage_items")
        for index, item in enumerate(coverage_items):
            goal = goals_by_id.get(item.coverage_goal_id)
            if goal is None:
                raise ValueError(
                    f"coverage_items[{index}].coverage_goal_id is unknown: {item.coverage_goal_id}"
                )
            if item.requirement_id != goal.requirement_id:
                raise ValueError(
                    f"coverage_items[{index}].requirement_id must match its coverage goal: "
                    f"{item.requirement_id} != {goal.requirement_id}"
                )
