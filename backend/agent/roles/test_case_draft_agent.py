from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ..core.agent_context import AgentContext
from ..core.agent_result import AgentResult
from ..core.base_agent import BaseAgent
from ..core.models import CoverageItem, RiskAnalysisItem, TestCaseDraft, TestDesignSpec
from ..tools.validation.id_gate import TC_ID_RE, require_id_format, require_unique_ids
from ..tools.validation.output_validator import validate_test_cases


MAX_QUALITY_REGENERATION_ATTEMPTS = 2
logger = logging.getLogger(__name__)


class TestCaseDraftAgent(BaseAgent):
    """Generate draft test cases from test design specifications."""

    async def run(self, context: AgentContext) -> AgentResult:
        try:
            if not context.test_design_specs:
                raise ValueError("test_design_specs are required.")

            started = time.perf_counter()
            self._repair_calls = 0
            spec_groups = self._group_specs_by_requirement(context.test_design_specs)
            logger.info(
                "TestCaseDraftAgent started: spec_count=%s requirement_group_count=%s",
                len(context.test_design_specs),
                len(spec_groups),
            )
            tasks = [
                self._process_requirement_group(specs, context)
                for specs in spec_groups
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_cases: list[TestCaseDraft] = []
            for result in results:
                if isinstance(result, BaseException):
                    raise result
                all_cases.extend(result)

            require_id_format(all_cases, "test_id", TC_ID_RE, "test_cases")
            require_unique_ids(all_cases, "test_id", "test_cases")
            context.test_cases = all_cases
            logger.info(
                "TestCaseDraftAgent completed: seconds=%.2f case_count=%s repair_calls=%s",
                time.perf_counter() - started,
                len(all_cases),
                self._repair_calls,
            )
            return AgentResult(success=True, data={"test_cases": all_cases})
        except Exception as exc:
            return AgentResult(success=False, data={}, error=str(exc))

    async def _process_requirement_group(
        self,
        specs: list[TestDesignSpec],
        context: AgentContext,
    ) -> list[TestCaseDraft]:
        accepted_cases: list[TestCaseDraft] = []
        for spec in specs:
            coverage = self._find_coverage_item(
                spec.coverage_item_id,
                context.coverage_items,
            )
            risk = self._find_risk_item(
                spec.requirement_id,
                context.risk_analysis,
            )
            generated = await self._generate_with_quality_loop(
                spec,
                coverage,
                risk,
                accepted_cases,
                context,
            )
            accepted_cases.extend(generated)
        return accepted_cases

    async def _generate_with_quality_loop(
        self,
        spec: TestDesignSpec,
        coverage: CoverageItem | dict,
        risk: RiskAnalysisItem | dict,
        accepted_cases: list[TestCaseDraft],
        context: AgentContext,
    ) -> list[TestCaseDraft]:
        quality_feedback = ""
        latest_cases: list[TestCaseDraft] = []

        for attempt in range(MAX_QUALITY_REGENERATION_ATTEMPTS + 1):
            latest_cases = await self._generate_candidate_cases(
                spec,
                coverage,
                risk,
                accepted_cases,
                quality_feedback,
                context,
            )
            try:
                self._validate_candidate_cases(latest_cases, spec, risk, accepted_cases)
            except ValueError as exc:
                if attempt >= MAX_QUALITY_REGENERATION_ATTEMPTS:
                    raise
                self._repair_calls += 1
                quality_feedback = str(exc)
                continue
            return latest_cases

        return latest_cases

    async def _generate_candidate_cases(
        self,
        spec: TestDesignSpec,
        coverage: CoverageItem | dict,
        risk: RiskAnalysisItem | dict,
        accepted_cases: list[TestCaseDraft],
        quality_feedback: str,
        context: AgentContext,
    ) -> list[TestCaseDraft]:
        test_cases = await self._run_validated_json_prompt(
            "test_case_draft",
            {
                "test_design_spec": spec,
                "coverage_item": coverage,
                "risk_item": risk,
                "existing_test_cases": self._case_summaries(accepted_cases),
                "quality_feedback": quality_feedback,
            },
            context,
            "test_cases",
            validate_test_cases,
        )
        return test_cases

    def _validate_candidate_cases(
        self,
        test_cases: list[TestCaseDraft],
        spec: TestDesignSpec,
        risk: RiskAnalysisItem | dict,
        accepted_cases: list[TestCaseDraft],
    ) -> None:
        if not test_cases:
            raise ValueError(
                "test_cases must contain at least one test case for "
                f"spec_id={spec.spec_id}, coverage_item_id={spec.coverage_item_id}."
            )
        existing_ids = {item.test_id for item in accepted_cases}
        require_id_format(test_cases, "test_id", TC_ID_RE, "test_cases")
        require_unique_ids(test_cases, "test_id", "test_cases")
        for index, test_case in enumerate(test_cases):
            if test_case.test_id in existing_ids:
                raise ValueError(
                    f"test_cases[{index}].test_id is already used by an earlier "
                    f"test case in this requirement: {test_case.test_id}"
                )
            if test_case.requirement_id != spec.requirement_id:
                raise ValueError(
                    f"test_cases[{index}].requirement_id must match test design spec: "
                    f"{test_case.requirement_id} != {spec.requirement_id}"
                )
            if test_case.coverage_item_id != spec.coverage_item_id:
                raise ValueError(
                    f"test_cases[{index}].coverage_item_id must match test design spec: "
                    f"{test_case.coverage_item_id} != {spec.coverage_item_id}"
                )
            if test_case.spec_id != spec.spec_id:
                raise ValueError(
                    f"test_cases[{index}].spec_id must match test design spec: "
                    f"{test_case.spec_id} != {spec.spec_id}"
                )
            if test_case.technique != spec.technique:
                raise ValueError(
                    f"test_cases[{index}].technique must match test design spec: "
                    f"{test_case.technique} != {spec.technique}"
                )
            if isinstance(risk, RiskAnalysisItem) and test_case.priority != risk.test_priority:
                raise ValueError(
                    f"test_cases[{index}].priority must match risk_item.test_priority: "
                    f"{test_case.priority} != {risk.test_priority}"
                )
            if test_case.status != "Draft":
                raise ValueError(f"test_cases[{index}].status must be Draft.")

    def _group_specs_by_requirement(
        self,
        specs: list[TestDesignSpec],
    ) -> list[list[TestDesignSpec]]:
        groups: dict[str, list[TestDesignSpec]] = {}
        order: list[str] = []
        for spec in specs:
            key = spec.requirement_id
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(spec)
        return [groups[key] for key in order]

    def _case_summaries(
        self,
        test_cases: list[TestCaseDraft],
        *,
        include_steps: bool = False,
    ) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for test_case in test_cases:
            summary = {
                "test_id": test_case.test_id,
                "requirement_id": test_case.requirement_id,
                "coverage_item_id": test_case.coverage_item_id,
                "spec_id": test_case.spec_id,
                "technique": test_case.technique,
                "title": test_case.title,
                "input_data": test_case.input_data,
                "expected_result": test_case.expected_result,
            }
            if include_steps:
                summary["test_steps"] = test_case.test_steps
            summaries.append(summary)
        return summaries

    def _find_coverage_item(
        self,
        coverage_item_id: str,
        coverage_items: list[CoverageItem],
    ) -> CoverageItem | dict:
        for coverage_item in coverage_items:
            if coverage_item.coverage_item_id == coverage_item_id:
                return coverage_item
        return {}

    def _find_risk_item(
        self,
        requirement_id: str,
        risk_analysis: list[RiskAnalysisItem],
    ) -> RiskAnalysisItem | dict:
        for risk_item in risk_analysis:
            if risk_item.requirement_id == requirement_id:
                return risk_item
        return {}
