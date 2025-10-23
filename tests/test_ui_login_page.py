def test_login_page_renders_when_flag_on(client_admin):
    r = client_admin.get("/ui/login", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    assert b"Superuser Login" in r.data


def test_login_page_404_when_flag_off(client_admin):
    app = client_admin.application
    registry = app.feature_registry
    if "inline_ui" in registry._flags:  # type: ignore[attr-defined]
        registry._flags.remove("inline_ui")  # type: ignore[attr-defined]
    r = client_admin.get("/ui/login", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 404
