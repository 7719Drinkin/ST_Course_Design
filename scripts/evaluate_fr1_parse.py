"""Evaluate FR1.1 requirement parsing output against D's 15-sample baseline."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPECTED_PATH = ROOT / "tests" / "data" / "aut_15_requirements.json"
EVALUATED_FIELDS = ("input_fields", "data_ranges", "conditions", "expected_action")


def normalize_text(value: Any) -> str:
    text = str(value).lower()
    text = re.sub(r"[^a-z0-9_.><=/-]+", " ", text)
    return " ".join(text.split())


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_text(item) for item in value if normalize_text(item)]
    return [normalize_text(value)] if normalize_text(value) else []


def token_set(value: Any) -> set[str]:
    if isinstance(value, list):
        text = " ".join(normalize_list(value))
    else:
        text = normalize_text(value)
    return {token for token in text.split() if token}


def score_list_field(expected: Any, actual: Any) -> float:
    expected_items = set(normalize_list(expected))
    actual_items = set(normalize_list(actual))

    if not expected_items:
        return 1.0 if not actual_items else 0.0
    if not actual_items:
        return 0.0

    matched = 0
    for expected_item in expected_items:
        expected_tokens = set(expected_item.split())
        if any(expected_item == actual_item or expected_tokens.issubset(set(actual_item.split())) for actual_item in actual_items):
            matched += 1

    return matched / len(expected_items)


def score_text_field(expected: Any, actual: Any) -> float:
    expected_tokens = token_set(expected)
    actual_tokens = token_set(actual)

    if not expected_tokens:
        return 1.0 if not actual_tokens else 0.0
    if not actual_tokens:
        return 0.0

    return len(expected_tokens & actual_tokens) / len(expected_tokens)


def score_field(field: str, expected: Any, actual: Any) -> float:
    if field == "expected_action":
        return score_text_field(expected, actual)
    return score_list_field(expected, actual)


def load_requirements(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"]: item for item in data}


def load_candidates(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates: dict[str, dict[str, Any]] = {}
    for item in data:
        requirement_id = item.get("requirement_id") or item.get("id")
        if requirement_id:
            candidates[requirement_id] = item
    return candidates


def evaluate(expected_path: Path, candidate_path: Path) -> dict[str, Any]:
    expected = load_requirements(expected_path)
    candidates = load_candidates(candidate_path)

    requirement_results = []
    field_totals = {field: 0.0 for field in EVALUATED_FIELDS}
    missing_requirements = []

    for requirement_id, expected_item in expected.items():
        candidate = candidates.get(requirement_id)
        if not candidate:
            missing_requirements.append(requirement_id)
            field_scores = {field: 0.0 for field in EVALUATED_FIELDS}
        else:
            field_scores = {
                field: score_field(field, expected_item.get(field), candidate.get(field))
                for field in EVALUATED_FIELDS
            }

        for field, score in field_scores.items():
            field_totals[field] += score

        requirement_results.append(
            {
                "requirement_id": requirement_id,
                "score": round(sum(field_scores.values()) / len(EVALUATED_FIELDS), 4),
                "field_scores": {field: round(score, 4) for field, score in field_scores.items()},
            }
        )

    requirement_count = len(expected)
    max_score = requirement_count * len(EVALUATED_FIELDS)
    total_score = sum(field_totals.values())
    field_accuracy = {
        field: round(total / requirement_count, 4)
        for field, total in field_totals.items()
    }

    return {
        "expected_path": str(expected_path),
        "candidate_path": str(candidate_path),
        "requirement_count": requirement_count,
        "evaluated_fields": list(EVALUATED_FIELDS),
        "overall_accuracy": round(total_score / max_score, 4),
        "field_accuracy": field_accuracy,
        "missing_requirements": missing_requirements,
        "results": requirement_results,
        "pass": total_score / max_score >= 0.8,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="B parse output JSON file")
    parser.add_argument(
        "--expected",
        type=Path,
        default=DEFAULT_EXPECTED_PATH,
        help="Expected requirement baseline JSON",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(args.expected, args.candidate)

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)

    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
