"""Shared fixtures for AUT API tests."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests

# Make project root and backend importable so tests can import from backend.*
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_TESTING_ROOT = _PROJECT_ROOT / "Testing"
if str(_TESTING_ROOT) not in sys.path:
    sys.path.insert(0, str(_TESTING_ROOT))
_BACKEND = _PROJECT_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "aut_api: tests that require the live AUT service")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "ragas: RAGAS evaluation tests")
    config.addinivalue_line("markers", "llm: tests that require LLM access")
    config.addinivalue_line("markers", "ep: AUT equivalence partitioning test")
    config.addinivalue_line("markers", "bva: AUT boundary value analysis test")
    config.addinivalue_line("markers", "dt: AUT decision table test")
    config.addinivalue_line("markers", "fsm: AUT finite state machine test")
    config.addinivalue_line("markers", "p1: AUT priority P1 test")
    config.addinivalue_line("markers", "p2: AUT priority P2 test")
    config.addinivalue_line("markers", "p3: AUT priority P3 test")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    try:
        from tests.aut.traceability import get_traceability
    except ModuleNotFoundError:
        return

    for item in items:
        test_name = getattr(item, "originalname", None) or item.name.split("[", 1)[0]
        traceability = get_traceability(test_name)
        if not traceability:
            continue

        for technique in traceability.get("techniques", []):
            item.add_marker(getattr(pytest.mark, technique.lower()))
        for priority in traceability.get("priorities", []):
            item.add_marker(getattr(pytest.mark, priority.lower()))

        item.user_properties.extend(
            [
                ("test_ids", ",".join(traceability.get("test_ids", []))),
                ("requirement_ids", ",".join(traceability.get("requirement_ids", []))),
                ("coverage_item_ids", ",".join(traceability.get("coverage_item_ids", []))),
                ("techniques", ",".join(traceability.get("techniques", []))),
                ("priorities", ",".join(traceability.get("priorities", []))),
            ]
        )


DEFAULT_AUT_BASE_URL = "http://localhost:8080"


@pytest.fixture(scope="session")
def aut_base_url() -> str:
    return os.getenv("AUT_BASE_URL", DEFAULT_AUT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def aut_session(aut_base_url: str) -> requests.Session:
    session = requests.Session()
    try:
        response = session.get(f"{aut_base_url}/api/books", timeout=3)
        response.raise_for_status()
    except requests.RequestException as exc:
        pytest.skip(f"AUT service is not reachable at {aut_base_url}: {exc}")
    return session


@pytest.fixture()
def unique_suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def today_iso() -> str:
    return date.today().isoformat()


@pytest.fixture()
def due_date_iso() -> str:
    return (date.today() + timedelta(days=14)).isoformat()


def book_payload(unique_suffix: str, available_copies: int = 2) -> dict:
    return {
        "title": f"Test Book {unique_suffix}",
        "author": "D Tester",
        "publicationYear": 2026,
        "genre": "Testing",
        "availableCopies": available_copies,
    }


def member_payload(unique_suffix: str) -> dict:
    return {
        "name": f"Member {unique_suffix}",
        "email": f"member-{unique_suffix}@example.com",
        "phoneNumber": "1234567890",
        "startDate": "2026-05-09",
        "endDate": "2027-05-09",
    }


def create_book(session: requests.Session, base_url: str, unique_suffix: str, available_copies: int = 2) -> dict:
    response = session.post(
        f"{base_url}/api/books",
        json=book_payload(unique_suffix, available_copies=available_copies),
        timeout=5,
    )
    assert response.status_code == 201
    return response.json()


def create_member(session: requests.Session, base_url: str, unique_suffix: str) -> dict:
    response = session.post(
        f"{base_url}/api/members",
        json=member_payload(unique_suffix),
        timeout=5,
    )
    assert response.status_code == 201
    return response.json()


def borrow_book(session: requests.Session, base_url: str, book_id: int, member_id: int) -> requests.Response:
    return session.post(
        f"{base_url}/api/borrow",
        json={"book": {"id": book_id}, "member": {"id": member_id}},
        timeout=5,
    )
