"""Borrowing and return workflow API tests for the AUT."""

from __future__ import annotations

import pytest

from tests.conftest import borrow_book, create_book, create_member


pytestmark = [pytest.mark.aut_api, pytest.mark.integration]


def test_list_borrowing_records_returns_json_array(aut_session, aut_base_url):
    response = aut_session.get(f"{aut_base_url}/api/borrowing-records", timeout=5)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_borrow_available_book_creates_record_and_decrements_copies(
    aut_session,
    aut_base_url,
    unique_suffix,
    today_iso,
    due_date_iso,
):
    book = create_book(aut_session, aut_base_url, unique_suffix, available_copies=2)
    member = create_member(aut_session, aut_base_url, unique_suffix)

    response = borrow_book(aut_session, aut_base_url, book["id"], member["id"])

    assert response.status_code == 201
    record = response.json()
    assert record["id"] > 0
    assert record["book"]["id"] == book["id"]
    assert record["member"]["id"] == member["id"]
    assert record["borrowDate"] == today_iso
    assert record["dueDate"] == due_date_iso
    assert record["returnDate"] is None
    assert record["book"]["availableCopies"] == 1

    fetched_book = aut_session.get(f"{aut_base_url}/api/books/{book['id']}", timeout=5).json()
    assert fetched_book["availableCopies"] == 1


def test_borrow_rejects_unknown_book(aut_session, aut_base_url, unique_suffix):
    member = create_member(aut_session, aut_base_url, unique_suffix)

    response = borrow_book(aut_session, aut_base_url, 99999999, member["id"])

    assert response.status_code == 400


def test_borrow_rejects_unknown_member(aut_session, aut_base_url, unique_suffix):
    book = create_book(aut_session, aut_base_url, unique_suffix, available_copies=1)

    response = borrow_book(aut_session, aut_base_url, book["id"], 99999999)

    assert response.status_code == 400


def test_borrow_rejects_missing_book_id(aut_session, aut_base_url, unique_suffix):
    member = create_member(aut_session, aut_base_url, unique_suffix)

    response = aut_session.post(
        f"{aut_base_url}/api/borrow",
        json={"book": {}, "member": {"id": member["id"]}},
        timeout=5,
    )

    assert response.status_code == 400


def test_borrow_rejects_missing_member_id(aut_session, aut_base_url, unique_suffix):
    book = create_book(aut_session, aut_base_url, unique_suffix, available_copies=1)

    response = aut_session.post(
        f"{aut_base_url}/api/borrow",
        json={"book": {"id": book["id"]}, "member": {}},
        timeout=5,
    )

    assert response.status_code == 400


def test_borrow_rejects_book_with_zero_available_copies(aut_session, aut_base_url, unique_suffix):
    book = create_book(aut_session, aut_base_url, unique_suffix, available_copies=0)
    member = create_member(aut_session, aut_base_url, unique_suffix)

    response = borrow_book(aut_session, aut_base_url, book["id"], member["id"])

    assert response.status_code == 400
    fetched_book = aut_session.get(f"{aut_base_url}/api/books/{book['id']}", timeout=5).json()
    assert fetched_book["availableCopies"] == 0


def test_return_borrowed_book_increments_available_copies(aut_session, aut_base_url, unique_suffix):
    book = create_book(aut_session, aut_base_url, unique_suffix, available_copies=1)
    member = create_member(aut_session, aut_base_url, unique_suffix)
    borrow_response = borrow_book(aut_session, aut_base_url, book["id"], member["id"])
    record_id = borrow_response.json()["id"]

    return_response = aut_session.put(f"{aut_base_url}/api/return/{record_id}", timeout=5)

    assert return_response.status_code == 200
    fetched_book = aut_session.get(f"{aut_base_url}/api/books/{book['id']}", timeout=5).json()
    assert fetched_book["availableCopies"] == 1


def test_return_unknown_record_returns_400(aut_session, aut_base_url):
    response = aut_session.put(f"{aut_base_url}/api/return/99999999", timeout=5)

    assert response.status_code == 400


def test_duplicate_return_is_rejected(aut_session, aut_base_url, unique_suffix):
    book = create_book(aut_session, aut_base_url, unique_suffix, available_copies=1)
    member = create_member(aut_session, aut_base_url, unique_suffix)
    borrow_response = borrow_book(aut_session, aut_base_url, book["id"], member["id"])
    record_id = borrow_response.json()["id"]

    first_return = aut_session.put(f"{aut_base_url}/api/return/{record_id}", timeout=5)
    second_return = aut_session.put(f"{aut_base_url}/api/return/{record_id}", timeout=5)

    assert first_return.status_code == 200
    assert second_return.status_code == 400


def test_malformed_json_request_returns_400(aut_session, aut_base_url):
    response = aut_session.post(
        f"{aut_base_url}/api/books",
        data="{bad-json",
        headers={"Content-Type": "application/json"},
        timeout=5,
    )

    assert response.status_code == 400
