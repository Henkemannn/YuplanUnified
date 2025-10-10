"""Add tests ensuring guards raise exceptions that central error handlers convert into unified envelopes (401/403), including required_role on 403."""

def test_guard_session_raises_401(client_no_tenant):
    # Access editor endpoint without any session headers -> unauthorized
    r = client_no_tenant.get("/_guard/editor")
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("status") == 401 and body.get("type"," ").endswith("/unauthorized")


def test_guard_roles_raises_403(client_admin):
    # Use admin endpoint with viewer role to force forbidden
    r = client_admin.get("/_guard/admin", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("status") == 403 and body.get("type"," ").endswith("/forbidden")
    assert body.get("required_role") == "admin"


def test_guard_roles_legacy_mapping(client_admin):
    # cook maps to viewer (canonical) so accessing editor endpoint should fail with required_role editor
    r = client_admin.get("/_guard/editor", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("status") == 403 and body.get("type"," ").endswith("/forbidden")
    assert body.get("required_role") == "editor"
