from __future__ import annotations


def test_cook_forbidden_without_flag(client_admin):
    # cook should be blocked when flag disabled (default)
    # ensure flag explicitly disabled (in case other tests enabled it earlier in session)
    client_admin.post("/features/set", json={"name": "allow_legacy_cook_create", "enabled": False}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    r = client_admin.post("/tasks/", json={"title": "No flag"}, headers={"X-User-Role":"cook","X-Tenant-Id":"1"})
    assert r.status_code == 403, r.get_data(as_text=True)
    body = r.get_data(as_text=True)
    assert '"required_role":"editor"' in body


def test_cook_allowed_with_flag(client_admin):
    # enable flag via admin user header
    client_admin.post("/features/set", json={"name": "allow_legacy_cook_create", "enabled": True}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    r = client_admin.post("/tasks/", json={"title": "With flag"}, headers={"X-User-Role":"cook","X-Tenant-Id":"1"})
    assert r.status_code in (200,201)
