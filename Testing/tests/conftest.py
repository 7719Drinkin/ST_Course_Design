"""Shared fixtures for AUT API tests."""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest
import requests


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
