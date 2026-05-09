"""Member Management API tests for the AUT."""

from __future__ import annotations

import pytest

from tests.conftest import create_member, member_payload


pytestmark = [pytest.mark.aut_api, pytest.mark.integration]


def test_list_members_returns_json_array(aut_session, aut_base_url):
    response = aut_session.get(f"{aut_base_url}/api/members", timeout=5)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_and_get_member_by_id(aut_session, aut_base_url, unique_suffix):
    created = create_member(aut_session, aut_base_url, unique_suffix)

    assert created["id"] > 0
    assert created["name"] == f"Member {unique_suffix}"
    assert created["email"] == f"member-{unique_suffix}@example.com"

    response = aut_session.get(f"{aut_base_url}/api/members/{created['id']}", timeout=5)

    assert response.status_code == 200
    fetched = response.json()
    assert fetched["id"] == created["id"]
    assert fetched["phoneNumber"] == "1234567890"


def test_get_missing_member_returns_404(aut_session, aut_base_url):
    response = aut_session.get(f"{aut_base_url}/api/members/99999999", timeout=5)

    assert response.status_code == 404


def test_update_existing_member_uses_path_id(aut_session, aut_base_url, unique_suffix):
    created = create_member(aut_session, aut_base_url, unique_suffix)
    update = member_payload(unique_suffix + "-updated")

    response = aut_session.put(f"{aut_base_url}/api/members/{created['id']}", json=update, timeout=5)

    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == created["id"]
    assert updated["name"] == f"Member {unique_suffix}-updated"


def test_update_missing_member_returns_404(aut_session, aut_base_url, unique_suffix):
    response = aut_session.put(
        f"{aut_base_url}/api/members/99999999",
        json=member_payload(unique_suffix),
        timeout=5,
    )

    assert response.status_code == 404


def test_delete_existing_member_then_get_returns_404(aut_session, aut_base_url, unique_suffix):
    created = create_member(aut_session, aut_base_url, unique_suffix)

    delete_response = aut_session.delete(f"{aut_base_url}/api/members/{created['id']}", timeout=5)
    get_response = aut_session.get(f"{aut_base_url}/api/members/{created['id']}", timeout=5)

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_delete_missing_member_returns_404(aut_session, aut_base_url):
    response = aut_session.delete(f"{aut_base_url}/api/members/99999999", timeout=5)

    assert response.status_code == 404
