from flask.testing import FlaskClient


def _h(role="admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_admin_layout_renders_site_context_indicator_and_version(client_admin: FlaskClient):
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Indicator texts present
    assert "Kund:" in html
    assert "Arbetsplats:" in html
    # Version exposure via data attribute or meta
    assert "data-site-context-version" in html or "name=\"current-site-id\"" in html
