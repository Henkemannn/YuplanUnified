def test_support_ui_superuser(client_superuser):
    r = client_superuser.get(
        "/admin/support/ui", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"}
    )
    assert r.status_code == 200
    assert b"Yuplan Support" in r.data
    assert b'/static/css/support.css' in r.data
    assert b'/static/js/support.js' in r.data
    assert b"fetch('../')" not in r.data
    assert b"<script>" not in r.data
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "unsafe-inline" not in csp


def test_support_static_assets_are_available_under_strict_csp(client_superuser):
    css = client_superuser.get("/static/css/support.css")
    js = client_superuser.get("/static/js/support.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert b"innerHTML" not in js.data
    assert b"textContent" in js.data
    assert b"replaceChildren" in js.data


def test_support_ui_admin_forbidden(client_admin):
    r = client_admin.get("/admin/support/ui", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code in (401, 403)


def test_support_ui_forbidden(client_user):
    r = client_user.get("/admin/support/ui", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert r.status_code in (401, 403)
