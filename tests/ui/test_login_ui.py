import re

from core.db import get_session
from core.models import Tenant, User
from werkzeug.security import generate_password_hash


def test_ui_login_accepts_legacy_mixed_case_email(client_admin):
    app = client_admin.application
    with app.app_context():
        db = get_session()
        try:
            tenant = db.query(Tenant).first()
            if not tenant:
                tenant = Tenant(name="Primary")
                db.add(tenant)
                db.flush()
            user = User(
                tenant_id=tenant.id,
                email="Legacy.Ui@Example.Com",
                username="legacy.ui@example.com",
                password_hash=generate_password_hash("UiPassw0rd!"),
                role="superuser",
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

    resp = client_admin.post(
        "/ui/login",
        data={"email": "legacy.ui@example.com", "password": "UiPassw0rd!"},
        follow_redirects=False,
    )

    assert resp.status_code in (301, 302)
    assert "/ui/systemadmin/dashboard" in (resp.headers.get("Location") or "")

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
