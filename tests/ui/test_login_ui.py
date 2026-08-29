import re
import pytest

from core.db import get_session
from core.models import Tenant, User, Site, Department
from werkzeug.security import generate_password_hash


def _seed_login_user(db, *, role: str, password: str = "UiPassw0rd!") -> str:
    tenant = db.query(Tenant).first()
    if not tenant:
        tenant = Tenant(name="Primary")
        db.add(tenant)
        db.flush()
    site = Site(id=f"site-{role}-{tenant.id}", name=f"Site {role}", tenant_id=tenant.id)
    db.add(site)
    db.flush()
    department_id = None
    if role == "unit_portal":
        department_id = f"dept-{role}-{tenant.id}"
        db.add(
            Department(
                id=department_id,
                site_id=site.id,
                name="Portal Dept",
                resident_count_mode="manual",
            )
        )
        db.flush()
    email = f"{role}.{tenant.id}@example.com"
    db.add(
        User(
            tenant_id=tenant.id,
            email=email.lower(),
            username=email.lower(),
            password_hash=generate_password_hash(password),
            role=role,
            department_id=department_id,
        )
    )
    db.commit()
    return email.lower()


@pytest.mark.parametrize(
    ("role", "expected_target"),
    [
        ("unit_portal", "/ui/portal/department/week"),
        ("staff", "/ui/portal/week"),
        ("department", "/ui/portal/week"),
        ("admin", "/ui/admin"),
        ("kitchen", "/ui/kitchen"),
        ("superuser", "/ui/systemadmin/dashboard"),
    ],
)
def test_ui_login_redirects_by_role(client_admin, role, expected_target):
    app = client_admin.application
    with app.app_context():
        db = get_session()
        try:
            email = _seed_login_user(db, role=role)
        finally:
            db.close()

    resp = client_admin.post(
        "/ui/login",
        data={"email": email, "password": "UiPassw0rd!"},
        follow_redirects=False,
    )

    assert resp.status_code in (301, 302)
    assert expected_target in (resp.headers.get("Location") or "")


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
