import re

def test_ui_login_redirects_to_auth_login(client_admin):
    r = client_admin.get("/ui/login?next=/ui/weekview")
    # Should redirect to /auth/login with next param
    assert r.status_code in (301, 302)
    loc = r.headers.get("Location") or ""
    assert "/auth/login" in loc and "next=%2Fui%2Fweekview" in loc

def test_auth_login_renders_polished_template(client_admin):
    r = client_admin.get("/auth/login")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Look for Yuplan brand marker or spinner/logo classes
    assert "Yuplan" in html or re.search(r"login-logo-spin|yp-logo|logo-proposal", html)
