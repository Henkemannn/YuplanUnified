import os
import uuid
import pytest
from sqlalchemy import text
from core.app_factory import create_app
from core.db import get_session
from core.models import Site, User, Tenant
from core.ui_blueprint import ADMIN_ROLES, KITCHEN_UI_ROLES
from werkzeug.security import generate_password_hash


def _seed_user(db, email: str, password: str, role: str = "superuser"):
    t = db.query(Tenant).first()
    if not t:
        t = Tenant(name="Primary")
        db.add(t)
        db.flush()
    u = db.query(User).filter(User.email == email.lower()).first()
    if not u:
        u = User(tenant_id=t.id, email=email.lower(), password_hash=generate_password_hash(password), role=role)
        db.add(u)
    else:
        u.role = role
        u.password_hash = generate_password_hash(password)
    db.commit()
    return u


def test_login_json_and_form_redirect(monkeypatch):
    # Ensure predictable env
    monkeypatch.setenv("APP_ENV", "dev")
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        _seed_user(db, email, "Passw0rd!", role="superuser")
        c = app.test_client()
        # JSON login -> 200
        rj = c.post("/auth/login", json={"email": email, "password": "Passw0rd!"}, headers={"Accept": "application/json"})
        assert rj.status_code == 200
        # Form login -> 302 redirect to systemadmin dashboard
        rf = c.post("/auth/login", data={"email": email, "password": "Passw0rd!"}, headers={"Accept": "text/html"}, follow_redirects=False)
        assert rf.status_code in (301, 302)
        loc = rf.headers.get("Location") or ""
        assert "/ui/systemadmin/dashboard" in loc


@pytest.mark.parametrize(
    ("role", "expected_target"),
    [
        ("kitchen", "/ui/kitchen"),
        ("cook", "/ui/kitchen"),
        ("admin", "/ui/admin"),
        ("superuser", "/ui/systemadmin/dashboard"),
    ],
)
def test_auth_login_html_redirects_by_role(monkeypatch, role, expected_target):
    monkeypatch.setenv("APP_ENV", "dev")
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            tenant = db.query(Tenant).first()
            if not tenant:
                tenant = Tenant(name="Primary")
                db.add(tenant)
                db.flush()
            site_id = None
            if role != "superuser":
                site_id = f"site-{role}-{tenant.id}"
                site = Site(id=site_id, name=f"Site {role}", tenant_id=tenant.id)
                db.add(site)
                db.flush()
            email = f"{role}.{uuid.uuid4().hex[:8]}@example.com"
            user = _seed_user(db, email, "Passw0rd!", role=role)
            if site_id:
                db.execute(text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                    "PRIMARY KEY (user_id, site_id))"
                ))
                db.execute(
                    text(
                        "INSERT OR REPLACE INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                        "VALUES (:uid, :tid, :sid)"
                    ),
                    {"uid": int(user.id), "tid": int(tenant.id), "sid": site_id},
                )
                db.commit()
            c = app.test_client()
            rf = c.post(
                "/auth/login",
                data={"email": email, "password": "Passw0rd!"},
                headers={"Accept": "text/html"},
                follow_redirects=False,
            )
        finally:
            db.close()

    assert rf.status_code in (301, 302)
    assert expected_target in (rf.headers.get("Location") or "")


def test_auth_login_role_constants_remain_unchanged() -> None:
    assert KITCHEN_UI_ROLES == ("kitchen", "cook", "admin", "superuser")
    assert ADMIN_ROLES == ("admin", "superuser")
