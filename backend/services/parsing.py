"""Requirement ingest and parsing service.

The current parser is a deterministic adapter over the project sample data.
It keeps the same service boundary that a later RAG/LLM parser can replace.
"""

from __future__ import annotations

import json
from typing import Any

from backend.data_loader import get_requirement, load_requirements
from backend.services.traceability import fr_id_for_requirement


def ingest_requirements(source_type: str, content: Any) -> dict[str, Any]:
    if source_type == "json" and isinstance(content, list):
        return {
            "requirements": [
                {
                    "requirement_id": item.get("id") or item.get("requirement_id", f"REQ-AUT-INPUT-{idx:03d}"),
                    "raw_requirement": item.get("raw_requirement", ""),
                    "source": item.get("source", "json_input"),
                }
                for idx, item in enumerate(content, start=1)
            ],
            "errors": [],
        }

    if source_type == "json" and isinstance(content, str) and content.strip():
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            return {"requirements": [], "errors": [f"Invalid JSON content: {exc.msg}"]}
        return ingest_requirements("json", parsed)

    if isinstance(content, str) and content.strip():
        return {
            "requirements": [
                {
                    "requirement_id": "REQ-AUT-PASTE-001",
                    "raw_requirement": content.strip(),
                    "source": "direct_input",
                }
            ],
            "errors": [],
        }

    return {
        "requirements": [
            {
                "requirement_id": req["id"],
                "raw_requirement": req["raw_requirement"],
                "source": "aut_15_requirements",
            }
            for req in load_requirements()
        ],
        "errors": [],
    }


def parse_requirement(requirement_id: str, raw_requirement: str = "") -> dict[str, Any]:
    req = get_requirement(requirement_id)
    if req is None:
        # Stub path for ad-hoc pasted requirements; RAG/LLM extraction should replace this.
        return {
            "requirement_id": requirement_id,
            "input_fields": [],
            "data_ranges": [],
            "conditions": [],
            "expected_action": "",
            "confidence": 0.5,
            "missing_fields": ["input_fields", "conditions", "expected_action"],
            "source_context_ids": [],
            "prompt_template_id": "PROMPT-FR1-V1",
            "retrieved_context_ids": [],
            "model_name": "stub-parser",
            "output_schema_version": "parse-v1",
        }

    missing = [field for field in ("input_fields", "conditions", "expected_action") if not req.get(field)]
    fr_id = fr_id_for_requirement(req)
    return {
        "requirement_id": req["id"],
        "input_fields": req.get("input_fields", []),
        "data_ranges": req.get("data_ranges", []),
        "conditions": req.get("conditions", []),
        "expected_action": req.get("expected_action", ""),
        "confidence": 0.88 if not missing else 0.72,
        "missing_fields": missing,
        "source_context_ids": [f"AUT_SRS:{fr_id}"],
        "prompt_template_id": "PROMPT-FR1-V1",
        "retrieved_context_ids": [f"AUT-SRS-001#{fr_id}"],
        "model_name": "reference-parser",
        "output_schema_version": "parse-v1",
    }
