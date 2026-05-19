"""Small in-memory AUT API used by live local pytest checks."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, request

from backend.services.aut_store import store

aut_bp = Blueprint("aut", __name__, url_prefix="/api")


def _body() -> dict:
    data = request.get_json(silent=False)
    if not isinstance(data, dict):
        abort(400, "JSON object body is required")
    return data


@aut_bp.get("/books")
def list_books():
    return jsonify(store.list_books())


@aut_bp.post("/books")
def create_book():
    return jsonify(store.create_book(_body())), 201


@aut_bp.get("/books/<int:book_id>")
def get_book(book_id: int):
    book = store.books.get(book_id)
    if book is None:
        abort(404)
    return jsonify(book)


@aut_bp.put("/books/<int:book_id>")
def update_book(book_id: int):
    book = store.update_book(book_id, _body())
    if book is None:
        abort(404)
    return jsonify(book)


@aut_bp.delete("/books/<int:book_id>")
def delete_book(book_id: int):
    if book_id not in store.books:
        abort(404)
    del store.books[book_id]
    return "", 204


@aut_bp.get("/members")
def list_members():
    return jsonify(store.list_members())


@aut_bp.post("/members")
def create_member():
    return jsonify(store.create_member(_body())), 201


@aut_bp.get("/members/<int:member_id>")
def get_member(member_id: int):
    member = store.members.get(member_id)
    if member is None:
        abort(404)
    return jsonify(member)


@aut_bp.put("/members/<int:member_id>")
def update_member(member_id: int):
    member = store.update_member(member_id, _body())
    if member is None:
        abort(404)
    return jsonify(member)


@aut_bp.delete("/members/<int:member_id>")
def delete_member(member_id: int):
    if member_id not in store.members:
        abort(404)
    del store.members[member_id]
    return "", 204


@aut_bp.get("/borrowing-records")
def list_borrowing_records():
    return jsonify(list(store.records.values()))


@aut_bp.post("/borrow")
def borrow_book():
    body = _body()
    book_id = body.get("book", {}).get("id") if isinstance(body.get("book"), dict) else None
    member_id = body.get("member", {}).get("id") if isinstance(body.get("member"), dict) else None
    if book_id is None or member_id is None:
        abort(400, "book.id and member.id are required")
    record = store.borrow(int(book_id), int(member_id))
    if record is None:
        abort(400, "Borrow request is not valid")
    return jsonify(record), 201


@aut_bp.put("/return/<int:record_id>")
def return_book(record_id: int):
    record = store.return_book(record_id)
    if record is None:
        abort(400, "Return request is not valid")
    return jsonify(record)
