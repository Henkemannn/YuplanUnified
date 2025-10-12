def test_support_ui_superuser(client_superuser):
    r = client_superuser.get(
        "/admin/support/ui", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"}
    )
    assert r.status_code == 200
    assert b"Yuplan Support" in r.data


def test_support_ui_admin_forbidden(client_admin):
    r = client_admin.get("/admin/support/ui", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code in (401, 403)


def test_support_ui_forbidden(client_user):
    r = client_user.get("/admin/support/ui", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert r.status_code in (401, 403)
