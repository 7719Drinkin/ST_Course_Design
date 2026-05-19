"""Shared traceability helpers for requirement, coverage, and test ids."""

from __future__ import annotations

from typing import Any


AREA_SLUGS = {
    "Book CRUD": "BOOK",
    "Member CRUD": "MEMBER",
    "Borrowing": "BORROW",
    "Return": "RETURN",
    "Records": "RECORDS",
    "Error Handling": "ERROR",
}


def coverage_id_for_requirement(req: dict[str, Any]) -> str:
    area_slug = AREA_SLUGS.get(req.get("area", ""), "GEN")
    suffix = req["id"].replace("REQ-AUT-", "")
    return f"COV-AUT-{area_slug}-{suffix.zfill(3)}"


def fr_id_for_requirement(req: dict[str, Any]) -> str:
    area_slug = AREA_SLUGS.get(req.get("area", ""), "GEN")
    return f"FR-AUT-{area_slug}-001"
