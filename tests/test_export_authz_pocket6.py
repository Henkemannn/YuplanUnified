"""Export API authz tests (P6.3 PR C)."""


def test_export_unauthorized_no_session(client_no_tenant):
    r = client_no_tenant.get("/export/notes.csv")
    assert r.status_code == 401
    body = r.get_data(as_text=True)  # CSV endpoints return JSON error envelope via handler
    assert '"status":401' in body and "/unauthorized" in body


def test_export_forbidden_viewer(client_admin):
    # viewer (canonical) should not export (requires editor or admin)
    r = client_admin.get("/export/notes.csv", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    assert r.status_code == 403
    txt = r.get_data(as_text=True)
    assert '"status":403' in txt and "/forbidden" in txt and '"required_role":"editor"' in txt


def test_export_happy_editor(client_admin):
    r = client_admin.get("/export/notes.csv", headers={"X-User-Role": "editor", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    # Response is CSV; first header row expected
    head = r.data.decode().splitlines()[0]
    assert "id" in head and "content" in head
