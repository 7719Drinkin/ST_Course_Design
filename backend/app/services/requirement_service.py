"""Requirement ingest and parse service."""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from backend.app.models.common import Technique
from backend.app.models.requirement import RequirementEntity
from backend.app.schemas.requirements import ParseResponse, RequirementResponse

REQUIRED_PARSE_FIELDS = ("input_fields", "data_ranges", "conditions", "expected_action")


def _requirement_response(entity: RequirementEntity) -> RequirementResponse:
    return RequirementResponse(
        requirement_id=entity.requirement_id,
        raw_requirement=entity.raw_requirement,
        source=entity.source,
    )


def _entity_from_external(item: dict[str, Any], index: int, source: str = "json_input") -> RequirementEntity:
    requirement_id = item.get("requirement_id") or item.get("id") or f"REQ-AUT-INPUT-{index:03d}"
    raw_requirement = item.get("raw_requirement") or item.get("text") or item.get("requirement") or ""
    techniques = _normalize_techniques(item.get("techniques"))
    return RequirementEntity(
        requirement_id=requirement_id,
        raw_requirement=raw_requirement,
        source=item.get("source", source),
        area=item.get("area") or item.get("module", "general"),
        title=item.get("title", requirement_id),
        input_fields=_normalize_string_list(item.get("input_fields")),
        data_ranges=_normalize_string_list(item.get("data_ranges")),
        conditions=_normalize_string_list(item.get("conditions")),
        expected_action=item.get("expected_action", ""),
        techniques=techniques,
        priority=item.get("priority") if item.get("priority") in {"High", "Medium", "Low"} else "Medium",
    )


def _normalize_techniques(value: Any) -> list[Technique]:
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        values = value
    else:
        values = ["EP"]
    allowed = {"EP", "BVA", "DT", "FSM"}
    techniques = [item for item in values if item in allowed]
    return techniques or ["EP"]


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,;|]", value) if item.strip()]
    return []


def _try_parse_json_content(content: str) -> list[RequirementEntity] | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        parsed = parsed.get("requirements", [parsed])
    if not isinstance(parsed, list):
        return None
    return [_entity_from_external(item, index) for index, item in enumerate(parsed, start=1) if isinstance(item, dict)]


def _try_parse_csv_content(content: str) -> list[RequirementEntity] | None:
    if "," not in content or "requirement" not in content.lower():
        return None
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return None
    return [_entity_from_external(row, index, source="csv_input") for index, row in enumerate(rows, start=1)]


def _parse_text_content(content: str) -> list[RequirementEntity]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return []
    return [
        RequirementEntity(
            requirement_id=f"REQ-AUT-PASTE-{index:03d}",
            raw_requirement=line,
            source="manual_input",
            area="manual",
            title=f"Manual requirement {index}",
        )
        for index, line in enumerate(lines, start=1)
    ]


class RequirementService:
    def ingest(self, source_type: str, content: Any) -> tuple[list[RequirementResponse], list[str]]:
        if isinstance(content, list):
            entities = [_entity_from_external(item, index) for index, item in enumerate(content, start=1)]
            return [_requirement_response(item) for item in entities], []

        if not isinstance(content, str) or not content.strip():
            return [], ["requirement content is empty"]

        json_entities = _try_parse_json_content(content)
        if json_entities is not None:
            return [_requirement_response(item) for item in json_entities], []

        csv_entities = _try_parse_csv_content(content)
        if csv_entities is not None:
            return [_requirement_response(item) for item in csv_entities], []

        text_entities = _parse_text_content(content)
        return [_requirement_response(item) for item in text_entities], []

    def parse(self, requirement_id: str, raw_requirement: str = "") -> ParseResponse:
        source = RequirementEntity(
            requirement_id=requirement_id,
            raw_requirement=raw_requirement,
            source="runtime_request",
            title=requirement_id,
            expected_action=_infer_expected_action(raw_requirement),
            input_fields=_infer_input_fields(raw_requirement),
            conditions=_infer_conditions(raw_requirement),
        )
        missing_fields = [field for field in REQUIRED_PARSE_FIELDS if getattr(source, field) in ("", [])]
        # TODO(RAG): Replace local parsing with retrieved context and LLM parser output.
        return ParseResponse(
            requirement_id=source.requirement_id,
            input_fields=source.input_fields,
            data_ranges=source.data_ranges,
            conditions=source.conditions,
            expected_action=source.expected_action or source.raw_requirement,
            confidence=0.0,
            missing_fields=missing_fields,
            source_context_ids=[],
            prompt_template_id="",
            retrieved_context_ids=[],
            model_name="",
            output_schema_version="parse-v1",
        )


def _infer_input_fields(text: str) -> list[str]:
    candidates = []
    for pattern in (r"\b[A-Za-z]+\.id\b", r"\bavailableCopies\b", r"\brecordId\b", r"\bid\b"):
        candidates.extend(re.findall(pattern, text))
    return list(dict.fromkeys(candidates))


def _infer_conditions(text: str) -> list[str]:
    lowered = text.lower()
    conditions = []
    if "existing" in lowered:
        conditions.append("Referenced resource exists")
    if "missing" in lowered or "does not reference" in lowered:
        conditions.append("Referenced resource may be missing")
    if "greater than 0" in lowered or "> 0" in lowered:
        conditions.append("Numeric value greater than 0")
    return conditions


def _infer_expected_action(text: str) -> str:
    return text.strip()


requirement_service = RequirementService()
