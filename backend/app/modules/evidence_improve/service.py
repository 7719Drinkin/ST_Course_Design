from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..util import evidence, make_id, next_index, now_iso, to_dicts
from ..store import TARGET_TO_COLLECTION, workflow_store
from .schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResult,
    AnalysisSummary,
    RegenerateRequest,
    RegenerateResponse,
    RevisionRecord,
    RevisionsRequest,
    RevisionsResponse,
)


class EvidenceImproveService:
    def save_revision(self, request: RevisionsRequest) -> RevisionsResponse:
        existing = workflow_store.get_list(request.session_id, "revisions")
        revision = RevisionRecord(
            revision_id=make_id("REV", next_index(existing, "revision_id", "REV")),
            session_id=request.session_id,
            target_type=request.target_type,
            target_id=request.target_id,
            before=request.before,
            after=request.after,
            reason=request.reason,
            created_by=request.created_by,
            created_at=now_iso(),
        )
        affected_ids = workflow_store.apply_revision_status(
            request.session_id,
            request.target_type,
            request.target_id,
            request.before,
            request.after,
        )
        workflow_store.save_many(request.session_id, "revisions", [revision], "revision_id")
        return RevisionsResponse(revision=revision, affected_ids=affected_ids)

    def regenerate(self, request: RegenerateRequest) -> RegenerateResponse:
        revision = workflow_store.find_revision(request.session_id, request.revision_id)
        if revision is None:
            raise HTTPException(status_code=404, detail=f"revision_id not found: {request.revision_id}")

        collection_info = TARGET_TO_COLLECTION.get(str(revision.get("target_type")))
        updated: dict[str, Any] = {}
        unchanged: dict[str, Any] = {}
        deprecated: dict[str, Any] = {}
        created: dict[str, Any] = {}

        if collection_info:
            collection, id_field = collection_info
            updated[collection] = [
                item
                for item in workflow_store.get_list(request.session_id, collection)
                if item.get(id_field) == revision.get("target_id")
            ]
            unchanged[collection] = [
                item
                for item in workflow_store.get_list(request.session_id, collection)
                if item.get(id_field) != revision.get("target_id")
            ]
        else:
            updated[str(revision.get("target_type"))] = [revision.get("after", {})]

        existing_evidence = workflow_store.get_list(request.session_id, "prompt_evidence")
        prompt_evidence = [
            evidence(
                request.session_id,
                "revision_regenerate",
                request.revision_id,
                {"revision": revision, "current_state": request.current_state},
                {
                    "created": created,
                    "updated": updated,
                    "unchanged": unchanged,
                    "deprecated": deprecated,
                },
                next_index(existing_evidence, "evidence_id", "PE-AUT"),
                "TODO: call B to interpret revision impact, then call E to regenerate only affected tests.",
            )
        ]
        workflow_store.save_many(request.session_id, "prompt_evidence", prompt_evidence, "evidence_id")
        return RegenerateResponse(
            session_id=request.session_id,
            created=created,
            updated=updated,
            unchanged=unchanged,
            deprecated=deprecated,
            prompt_evidence=prompt_evidence,
        )

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        requirements = to_dicts(request.requirements) or workflow_store.get_list(request.session_id, "requirements")
        coverage_items = to_dicts(request.coverage_items) or workflow_store.get_list(request.session_id, "coverage_items")
        strategies = to_dicts(request.strategies) or workflow_store.get_list(request.session_id, "strategies")
        test_cases = to_dicts(request.test_cases) or workflow_store.get_list(request.session_id, "test_cases")
        revisions = to_dicts(request.revisions) or workflow_store.get_list(request.session_id, "revisions")

        revised_ids = {item.get("target_id") for item in revisions}
        strategies_by_coverage: dict[str, list[dict[str, Any]]] = {}
        for strategy in strategies:
            strategies_by_coverage.setdefault(str(strategy.get("coverage_item_id")), []).append(strategy)
        tests_by_coverage: dict[str, list[dict[str, Any]]] = {}
        for test_case in test_cases:
            tests_by_coverage.setdefault(str(test_case.get("coverage_item_id")), []).append(test_case)

        results: list[AnalysisResult] = []
        for requirement in requirements:
            requirement_id = str(requirement.get("requirement_id"))
            related_coverage = [
                item for item in coverage_items if item.get("requirement_id") == requirement_id
            ]
            if not related_coverage:
                results.append(
                    AnalysisResult(
                        requirement_id=requirement_id,
                        status="missing",
                        gap="No COV-AUT coverage item is mapped to this requirement.",
                    )
                )
                continue

            for coverage in related_coverage:
                coverage_id = str(coverage.get("coverage_item_id"))
                related_tests = tests_by_coverage.get(coverage_id, [])
                related_strategies = strategies_by_coverage.get(coverage_id, [])
                strategy_id = str((related_strategies[0] if related_strategies else {}).get("strategy_id") or "")
                if not related_tests:
                    results.append(
                        AnalysisResult(
                            requirement_id=requirement_id,
                            coverage_item_id=coverage_id,
                            strategy_id=strategy_id,
                            status="needs_review",
                            gap="Coverage item has no generated test case.",
                        )
                    )
                    continue

                for test_case in related_tests:
                    test_id = str(test_case.get("test_id"))
                    improved = bool({requirement_id, coverage_id, test_id} & revised_ids)
                    results.append(
                        AnalysisResult(
                            requirement_id=requirement_id,
                            coverage_item_id=coverage_id,
                            strategy_id=str(test_case.get("strategy_id") or strategy_id),
                            test_id=test_id,
                            status="improved" if improved else "covered",
                            gap="",
                            improvement="Human revision affected this mapping." if improved else "",
                        )
                    )

        if not requirements:
            for test_case in test_cases:
                results.append(
                    AnalysisResult(
                        requirement_id=str(test_case.get("requirement_id") or ""),
                        coverage_item_id=str(test_case.get("coverage_item_id") or ""),
                        strategy_id=str(test_case.get("strategy_id") or ""),
                        test_id=str(test_case.get("test_id") or ""),
                        status="needs_review" if not test_case.get("requirement_id") else "covered",
                        gap="" if test_case.get("requirement_id") else "Test case has no requirement mapping.",
                    )
                )

        summary = AnalysisSummary(
            requirements_count=len(requirements),
            coverage_items_count=len(coverage_items),
            test_cases_count=len(test_cases),
            missing_count=sum(1 for item in results if item.status == "missing"),
            improved_count=sum(1 for item in results if item.status == "improved"),
        )
        workflow_store.save_many(request.session_id, "analysis_results", results, replace_all=True)
        return AnalysisResponse(
            session_id=request.session_id,
            analysis_results=results,
            summary=summary,
        )
