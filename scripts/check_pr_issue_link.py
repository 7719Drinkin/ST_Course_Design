"""Validate that a pull request body references a GitHub Issue."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ISSUE_REFERENCE_PATTERN = re.compile(
    r"(?i)\b(close[sd]?|fix(e[sd])?|resolve[sd]?|refs?|related)\s+#\d+\b"
)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_pr_issue_link.py <github_event_path>")
        return 2

    event_path = Path(sys.argv[1])
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pull_request = event.get("pull_request") or {}
    body = pull_request.get("body") or ""

    if ISSUE_REFERENCE_PATTERN.search(body):
        print("PR body references a GitHub Issue.")
        return 0

    print(
        "PR body must reference a GitHub Issue using a phrase such as "
        "'Closes #123', 'Fixes #123', 'Resolves #123', 'Refs #123', or 'Related #123'."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
