"""In-memory AUT store used by local API tests and demos."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any


class AutStore:
    def __init__(self) -> None:
        self.books: dict[int, dict[str, Any]] = {}
        self.members: dict[int, dict[str, Any]] = {}
        self.records: dict[int, dict[str, Any]] = {}
        self.next_book_id = 1
        self.next_member_id = 1
        self.next_record_id = 1

    def list_books(self) -> list[dict[str, Any]]:
        return list(deepcopy(self.books).values())

    def create_book(self, payload: dict[str, Any]) -> dict[str, Any]:
        book = {"id": self.next_book_id, **payload}
        self.books[self.next_book_id] = book
        self.next_book_id += 1
        return deepcopy(book)

    def update_book(self, book_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        if book_id not in self.books:
            return None
        self.books[book_id] = {"id": book_id, **payload}
        return deepcopy(self.books[book_id])

    def list_members(self) -> list[dict[str, Any]]:
        return list(deepcopy(self.members).values())

    def create_member(self, payload: dict[str, Any]) -> dict[str, Any]:
        member = {"id": self.next_member_id, **payload}
        self.members[self.next_member_id] = member
        self.next_member_id += 1
        return deepcopy(member)

    def update_member(self, member_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        if member_id not in self.members:
            return None
        self.members[member_id] = {"id": member_id, **payload}
        return deepcopy(self.members[member_id])

    def borrow(self, book_id: int, member_id: int) -> dict[str, Any] | None:
        book = self.books.get(book_id)
        member = self.members.get(member_id)
        if not book or not member or book.get("availableCopies", 0) <= 0:
            return None

        book["availableCopies"] -= 1
        today = date.today()
        record = {
            "id": self.next_record_id,
            "book": deepcopy(book),
            "member": deepcopy(member),
            "borrowDate": today.isoformat(),
            "dueDate": (today + timedelta(days=14)).isoformat(),
            "returnDate": None,
        }
        self.records[self.next_record_id] = record
        self.next_record_id += 1
        return deepcopy(record)

    def return_book(self, record_id: int) -> dict[str, Any] | None:
        record = self.records.get(record_id)
        if not record or record["returnDate"] is not None:
            return None
        record["returnDate"] = date.today().isoformat()
        book_id = record["book"]["id"]
        if book_id in self.books:
            self.books[book_id]["availableCopies"] += 1
            record["book"] = deepcopy(self.books[book_id])
        return deepcopy(record)


store = AutStore()
