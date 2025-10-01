def test_inline_ui_page_renders(client_admin):
    r = client_admin.get("/ui/inline", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 200
    assert b"Inline UI" in r.data
    assert b"Notes" in r.data
    assert b"Tasks" in r.data


def test_ui_inline_flag_off_returns_404(client_admin):
    # Simulate flag off by removing from registry for this app instance
    app = client_admin.application
    registry = app.feature_registry
    if "inline_ui" in registry._flags:  # type: ignore[attr-defined]
        registry._flags.remove("inline_ui")  # type: ignore[attr-defined]
    r = client_admin.get("/ui/inline", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 404
    data = r.get_json()
    assert data["error"] == "not_found"
