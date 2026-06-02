from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import CoverageItem, RiskAnalysisItem, TestDesignSpec
from ..tools.validation.id_gate import SPEC_ID_RE, require_id_format, require_unique_ids
from ..tools.validation.output_validator import validate_test_design_specs


MAX_ID_REPAIR_ATTEMPTS = 2
logger = logging.getLogger(__name__)


class TestDesignSpecAgent(BaseAgent):
    """Expand coverage items into test design specifications without rewriting LLM IDs."""

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            if not context.coverage_items:
                raise ValueError("coverage_items are required.")

            started = time.perf_counter()
            groups = self._group_items_by_requirement(context.coverage_items)
            logger.info(
                "TestDesignSpecAgent started: coverage_item_count=%s requirement_group_count=%s",
                len(context.coverage_items),
                len(groups),
            )

            all_specs: list[TestDesignSpec] = []
            tasks = [
                self._process_requirement_group(group, context)
                for group in groups
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    raise result
                all_specs.extend(result)

            require_id_format(all_specs, "spec_id", SPEC_ID_RE, "test_design_specs")
            require_unique_ids(all_specs, "spec_id", "test_design_specs")
            context.test_design_specs = all_specs
            logger.info(
                "TestDesignSpecAgent completed: seconds=%.2f spec_count=%s",
                time.perf_counter() - started,
                len(all_specs),
            )
            return AgentResult(success=True, data={"test_design_specs": all_specs})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    async def _process_requirement_group(
        self,
        coverage_items: list[CoverageItem],
        context: AgentContext,
    ) -> list[TestDesignSpec]:
        accepted_specs: list[TestDesignSpec] = []
        for item in coverage_items:
            generated = await self._process_one(item, context, accepted_specs)
            accepted_specs.extend(generated)
        return accepted_specs

    async def _process_one(
        self,
        item: CoverageItem,
        context: AgentContext,
        accepted_specs: list[TestDesignSpec],
    ) -> list[TestDesignSpec]:
        risk = self._find_risk_item(item.requirement_id, context.risk_analysis)
        quality_feedback = ""
        specs: list[TestDesignSpec] = []
        for attempt in range(MAX_ID_REPAIR_ATTEMPTS + 1):
            specs = await self._run_validated_json_prompt(
                "test_design_spec",
                {
                    "coverage_item": item,
                    "rag_context": context.rag_context or "",
                    "risk_item": risk,
                    "existing_test_design_specs": self._spec_summaries(accepted_specs),
                    "quality_feedback": quality_feedback,
                },
                context,
                "test_design_specs",
                validate_test_design_specs,
            )
            try:
                self._validate_specs_for_coverage_item(specs, item, accepted_specs)
                return specs
            except ValueError as exc:
                if attempt >= MAX_ID_REPAIR_ATTEMPTS:
                    raise
                quality_feedback = str(exc)
        return specs

    def _validate_specs_for_coverage_item(
        self,
        specs: list[TestDesignSpec],
        coverage_item: CoverageItem,
        accepted_specs: list[TestDesignSpec],
    ) -> None:
        existing_ids = {item.spec_id for item in accepted_specs}
        require_id_format(specs, "spec_id", SPEC_ID_RE, "test_design_specs")
        require_unique_ids(specs, "spec_id", "test_design_specs")
        for index, spec in enumerate(specs):
            if spec.spec_id in existing_ids:
                raise ValueError(
                    f"test_design_specs[{index}].spec_id is already used by an earlier "
                    f"test design spec in this requirement: {spec.spec_id}"
                )
            if spec.requirement_id != coverage_item.requirement_id:
                raise ValueError(
                    f"test_design_specs[{index}].requirement_id must match coverage item: "
                    f"{spec.requirement_id} != {coverage_item.requirement_id}"
                )
            if spec.coverage_item_id != coverage_item.coverage_item_id:
                raise ValueError(
                    f"test_design_specs[{index}].coverage_item_id must match coverage item: "
                    f"{spec.coverage_item_id} != {coverage_item.coverage_item_id}"
                )
            if spec.technique != coverage_item.technique:
                raise ValueError(
                    f"test_design_specs[{index}].technique must match coverage item: "
                    f"{spec.technique} != {coverage_item.technique}"
                )

    def _group_items_by_requirement(
        self,
        coverage_items: list[CoverageItem],
    ) -> list[list[CoverageItem]]:
        groups: dict[str, list[CoverageItem]] = {}
        order: list[str] = []
        for item in coverage_items:
            key = item.requirement_id
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(item)
        return [groups[key] for key in order]

    def _spec_summaries(self, specs: list[TestDesignSpec]) -> list[dict[str, Any]]:
        return [
            {
                "spec_id": spec.spec_id,
                "coverage_item_id": spec.coverage_item_id,
                "requirement_id": spec.requirement_id,
                "technique": spec.technique,
            }
            for spec in specs
        ]

    def _find_risk_item(
        self,
        requirement_id: str,
        risk_analysis: list[RiskAnalysisItem],
    ) -> RiskAnalysisItem | dict:
        for risk_item in risk_analysis:
            if risk_item.requirement_id == requirement_id:
                return risk_item
        return {}
