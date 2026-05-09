"""Book Management API tests for the AUT."""

from __future__ import annotations

import pytest

from tests.conftest import book_payload, create_book


pytestmark = [pytest.mark.aut_api, pytest.mark.integration]


def test_list_books_returns_json_array(aut_session, aut_base_url):
    response = aut_session.get(f"{aut_base_url}/api/books", timeout=5)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_and_get_book_by_id(aut_session, aut_base_url, unique_suffix):
    created = create_book(aut_session, aut_base_url, unique_suffix, available_copies=3)

    assert created["id"] > 0
    assert created["title"] == f"Test Book {unique_suffix}"
    assert created["availableCopies"] == 3

    response = aut_session.get(f"{aut_base_url}/api/books/{created['id']}", timeout=5)

    assert response.status_code == 200
    fetched = response.json()
    assert fetched["id"] == created["id"]
    assert fetched["author"] == "D Tester"


def test_get_missing_book_returns_404(aut_session, aut_base_url):
    response = aut_session.get(f"{aut_base_url}/api/books/99999999", timeout=5)

    assert response.status_code == 404


def test_update_existing_book_uses_path_id(aut_session, aut_base_url, unique_suffix):
    created = create_book(aut_session, aut_base_url, unique_suffix)
    update = book_payload(unique_suffix + "-updated", available_copies=5)

    response = aut_session.put(f"{aut_base_url}/api/books/{created['id']}", json=update, timeout=5)

    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == created["id"]
    assert updated["title"] == f"Test Book {unique_suffix}-updated"
    assert updated["availableCopies"] == 5


def test_update_missing_book_returns_404(aut_session, aut_base_url, unique_suffix):
    response = aut_session.put(
        f"{aut_base_url}/api/books/99999999",
        json=book_payload(unique_suffix),
        timeout=5,
    )

    assert response.status_code == 404


def test_delete_existing_book_then_get_returns_404(aut_session, aut_base_url, unique_suffix):
    created = create_book(aut_session, aut_base_url, unique_suffix)

    delete_response = aut_session.delete(f"{aut_base_url}/api/books/{created['id']}", timeout=5)
    get_response = aut_session.get(f"{aut_base_url}/api/books/{created['id']}", timeout=5)

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_delete_missing_book_returns_404(aut_session, aut_base_url):
    response = aut_session.delete(f"{aut_base_url}/api/books/99999999", timeout=5)

    assert response.status_code == 404
