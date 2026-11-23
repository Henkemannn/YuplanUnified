from __future__ import annotations


def test_legacy_task_route_is_quarantined_when_flag_disabled(client_admin):
    set_response = client_admin.post(
        "/features/set",
        json={"name": "allow_legacy_cook_create", "enabled": False},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert set_response.status_code == 200
    assert set_response.get_json()["enabled"] is False

    check_response = client_admin.get(
        "/features/check?name=allow_legacy_cook_create",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert check_response.status_code == 200
    assert check_response.get_json()["enabled"] is False

    post_response = client_admin.post(
        "/tasks/", json={"title": "No flag"}, headers={"X-User-Role": "cook", "X-Tenant-Id": "1"}
    )
    assert post_response.status_code == 404
    assert post_response.get_json()["detail"] == "not_found"


def test_legacy_task_route_is_quarantined_when_flag_enabled(client_admin):
    set_response = client_admin.post(
        "/features/set",
        json={"name": "allow_legacy_cook_create", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert set_response.status_code == 200
    assert set_response.get_json()["enabled"] is True

    check_response = client_admin.get(
        "/features/check?name=allow_legacy_cook_create",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert check_response.status_code == 200
    assert check_response.get_json()["enabled"] is True

    post_response = client_admin.post(
        "/tasks/", json={"title": "With flag"}, headers={"X-User-Role": "cook", "X-Tenant-Id": "1"}
    )
    assert post_response.status_code == 404
    assert post_response.get_json()["detail"] == "not_found"
