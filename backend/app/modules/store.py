from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel


SESSION_LIST_KEYS = {
    "requirements",
    "parsed_requirements",
    "analyzed_requirements",
    "concepts",
    "risk_analysis",
    "risk_results",
    "coverage_goals",
    "coverage_items",
    "strategies",
    "test_design_specs",
    "test_cases",
    "fsm_test_cases",
    "prompt_evidence",
    "revisions",
    "analysis_results",
    "oracle_results",
}

SESSION_OBJECT_KEYS = {"optimization_result", "fsm", "requirement_input", "pipeline_status"}

ID_FIELDS = {
    "requirements": "requirement_id",
    "parsed_requirements": "requirement_id",
    "analyzed_requirements": "requirement_id",
    "concepts": "concept_id",
    "risk_analysis": "requirement_id",
    "risk_results": "target_id",
    "coverage_goals": "coverage_goal_id",
    "coverage_items": "coverage_item_id",
    "strategies": "strategy_id",
    "test_design_specs": "spec_id",
    "test_cases": "test_id",
    "fsm_test_cases": "test_id",
    "prompt_evidence": "evidence_id",
    "revisions": "revision_id",
    "analysis_results": None,
    "oracle_results": "test_id",
}

TARGET_TO_COLLECTION = {
    "requirement": ("requirements", "requirement_id"),
    "parsed_requirement": ("parsed_requirements", "requirement_id"),
    "risk_result": ("risk_results", "target_id"),
    "coverage_item": ("coverage_items", "coverage_item_id"),
    "strategy": ("strategies", "strategy_id"),
    "test_case": ("test_cases", "test_id"),
}


class WorkflowStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, dict[str, Any]] = {}

    def session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    **{key: [] for key in SESSION_LIST_KEYS},
                    **{key: None for key in SESSION_OBJECT_KEYS},
                }
            return self._sessions[session_id]

    def get_list(
        self,
        session_id: str,
        key: str,
        ids: list[str] | None = None,
        id_field: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = deepcopy(self.session(session_id).get(key, []))
        if not ids:
            return items
        selected = set(str(item) for item in ids)
        field = id_field or ID_FIELDS.get(key)
        if not field:
            return items
        return [item for item in items if str(item.get(field)) in selected]

    def save_many(
        self,
        session_id: str,
        key: str,
        items: list[Any],
        id_field: str | None = None,
        replace_all: bool = False,
    ) -> list[dict[str, Any]]:
        normalized = [_to_dict(item) for item in items]
        with self._lock:
            session = self.session(session_id)
            if replace_all or key not in session or not isinstance(session[key], list):
                session[key] = normalized
                return deepcopy(normalized)

            field = id_field or ID_FIELDS.get(key)
            if not field:
                session[key].extend(normalized)
                return deepcopy(normalized)

            existing = session[key]
            positions = {
                str(item.get(field)): index
                for index, item in enumerate(existing)
                if item.get(field) is not None
            }
            for item in normalized:
                item_id = str(item.get(field) or "")
                if item_id and item_id in positions:
                    existing[positions[item_id]] = item
                else:
                    existing.append(item)
                    if item_id:
                        positions[item_id] = len(existing) - 1
            return deepcopy(normalized)

    def save_object(self, session_id: str, key: str, value: Any) -> dict[str, Any] | None:
        normalized = _to_dict(value) if value is not None else None
        with self._lock:
            self.session(session_id)[key] = normalized
            return deepcopy(normalized)

    def clear_keys(self, session_id: str, keys: list[str]) -> None:
        """Clear selected collections/objects in one session.

        This is used when a new pipeline run starts so old downstream artifacts
        cannot be mixed with fresh parse output.
        """

        with self._lock:
            session = self.session(session_id)
            for key in keys:
                if key in SESSION_LIST_KEYS:
                    session[key] = []
                elif key in SESSION_OBJECT_KEYS:
                    session[key] = None

    def start_pipeline_run(self, session_id: str) -> str:
        run_id = f"RUN-{uuid4().hex[:12]}"
        now = _now_iso()
        status = {
            "run_id": run_id,
            "status": "running",
            "current_stage": "parse_requirements",
            "completed_stages": [],
            "failed_stage": "",
            "error": "",
            "started_at": now,
            "updated_at": now,
        }
        with self._lock:
            self.session(session_id)["pipeline_status"] = status
        return run_id

    def get_pipeline_status(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            status = deepcopy(self.session(session_id).get("pipeline_status"))
        if isinstance(status, dict) and status:
            return status
        return {
            "run_id": "",
            "status": "idle",
            "current_stage": "",
            "completed_stages": [],
            "failed_stage": "",
            "error": "",
            "started_at": "",
            "updated_at": "",
        }

    def is_current_pipeline_run(self, session_id: str, run_id: str) -> bool:
        status = self.get_pipeline_status(session_id)
        return bool(run_id) and status.get("run_id") == run_id and status.get("status") == "running"

    def apply_if_current_pipeline_run(self, session_id: str, run_id: str, callback) -> bool:
        """Run a store mutation only while the given run_id is still current."""

        with self._lock:
            status = self.session(session_id).get("pipeline_status")
            if not isinstance(status, dict):
                return False
            if status.get("run_id") != run_id or status.get("status") != "running":
                return False
            callback()
            return True

    def complete_pipeline_stage(
        self,
        session_id: str,
        run_id: str,
        stage: str,
        next_stage: str = "",
    ) -> None:
        with self._lock:
            status = self.session(session_id).get("pipeline_status")
            if not isinstance(status, dict) or status.get("run_id") != run_id:
                return
            completed = list(status.get("completed_stages") or [])
            if stage not in completed:
                completed.append(stage)
            status.update(
                {
                    "status": "running",
                    "current_stage": next_stage,
                    "completed_stages": completed,
                    "updated_at": _now_iso(),
                }
            )

    def finish_pipeline_run(self, session_id: str, run_id: str) -> None:
        with self._lock:
            status = self.session(session_id).get("pipeline_status")
            if not isinstance(status, dict) or status.get("run_id") != run_id:
                return
            completed = list(status.get("completed_stages") or [])
            if "final_validation" not in completed:
                completed.append("final_validation")
            status.update(
                {
                    "status": "completed",
                    "current_stage": "",
                    "completed_stages": completed,
                    "failed_stage": "",
                    "error": "",
                    "updated_at": _now_iso(),
                }
            )

    def fail_pipeline_run(self, session_id: str, run_id: str, stage: str, error: str) -> None:
        with self._lock:
            status = self.session(session_id).get("pipeline_status")
            if not isinstance(status, dict) or status.get("run_id") != run_id:
                return
            status.update(
                {
                    "status": "failed",
                    "current_stage": "",
                    "failed_stage": stage,
                    "error": error,
                    "updated_at": _now_iso(),
                }
            )

    def get_object(self, session_id: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            return deepcopy(self.session(session_id).get(key))

    def find_revision(self, session_id: str, revision_id: str) -> dict[str, Any] | None:
        for item in self.get_list(session_id, "revisions"):
            if item.get("revision_id") == revision_id:
                return item
        return None

    def apply_revision_status(
        self,
        session_id: str,
        target_type: str,
        target_id: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> list[str]:
        collection = TARGET_TO_COLLECTION.get(target_type)
        if not collection:
            return [target_id]

        key, id_field = collection
        existing_items = self.get_list(session_id, key, [target_id], id_field)
        if not existing_items:
            return [target_id]
        revised = dict(existing_items[0])
        revised.update(after)
        revised.setdefault(id_field, target_id)
        revision_status = "human_added" if not before else "human_revised"
        if key == "coverage_items":
            revised["status"] = revision_status
        elif key == "test_cases":
            revised["review_status"] = revision_status
        else:
            revised["revision_status"] = revision_status
        self.save_many(session_id, key, [revised], id_field=id_field)
        return [target_id]

    def export_bundle(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = deepcopy(self.session(session_id))
        return {
            "requirements": session.get("requirements", []),
            "risk_results": session.get("risk_results", []),
            "coverage_items": session.get("coverage_items", []),
            "strategies": session.get("strategies", []),
            "test_design_specs": session.get("test_design_specs", []),
            "test_cases": session.get("test_cases", []),
            "fsm": session.get("fsm"),
            "fsm_test_cases": session.get("fsm_test_cases", []),
            "optimization_result": session.get("optimization_result"),
            "revisions": session.get("revisions", []),
            "prompt_evidence": session.get("prompt_evidence", []),
            "analysis_results": session.get("analysis_results", []),
            "oracle_results": session.get("oracle_results", []),
        }


def _to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, BaseModel):
        return item.model_dump(mode="json", by_alias=True)
    if isinstance(item, dict):
        return deepcopy(item)
    if hasattr(item, "to_dict"):
        return item.to_dict()
    raise TypeError(f"Unsupported store item type: {type(item)!r}")


workflow_store = WorkflowStore()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
