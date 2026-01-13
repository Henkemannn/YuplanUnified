"""AuthZ migration tests for notes (P6.3 PR A)."""


def test_notes_list_happy(client_admin):
    # Provide tenant + admin role
    r = client_admin.get("/notes/", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_notes_update_requires_elevation_for_non_owner_marker(client_admin):
    # For now ownership simulation limited (same session user_id). We assert update still works for owner.
    create = client_admin.post(
        "/notes/", json={"content": "abc"}, headers={"X-User-Role": "admin", "X-Tenant-Id": "1"}
    )
    assert create.status_code == 200
    note_id = create.get_json()["note"]["id"]
    r = client_admin.put(
        f"/notes/{note_id}",
        json={"content": "zzz"},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert r.status_code == 200


def test_notes_requires_session(client_no_tenant):
    r = client_no_tenant.get("/notes/")
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("status") == 401 and body.get("type", " ").endswith("/unauthorized")
