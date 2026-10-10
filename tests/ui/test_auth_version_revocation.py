from __future__ import annotations

import os
import tempfile
import uuid
import re

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import create_all, get_session
from core.jwt_utils import decode as jwt_decode
from core.models import Site, Tenant, User


def _csrf_from_html(html: str) -> str:
    marker = 'name="csrf_token" value="'
    start = html.find(marker)
    assert start != -1, "csrf_token missing from rendered HTML"
    start += len(marker)
    end = html.find('"', start)
    assert end != -1, "csrf_token value not terminated"
    return html[start:end]


def _make_app():
    fd, db_path = tempfile.mkstemp(prefix="auth_version_", suffix=".db")
    os.close(fd)
    url = f"sqlite:///{db_path}"
    app = create_app({"TESTING": True, "database_url": url, "FORCE_DB_REINIT": True})
    with app.app_context():
        create_all()
    return app


def _seed_user(db, *, email: str, password: str, role: str, tenant_id: int, site_id: str) -> User:
    user = User(
        tenant_id=tenant_id,
        email=email,
        username=email,
        password_hash=generate_password_hash(password),
        role=role,
        full_name=email.split("@", 1)[0],
    )
    db.add(user)
    db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
            "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
            "PRIMARY KEY (user_id, site_id))"
        )
    )
    db.flush()
    db.execute(
        text(
            "INSERT OR REPLACE INTO kitchen_user_sites (user_id, tenant_id, site_id) "
            "VALUES (:uid, :tid, :sid)"
        ),
        {"uid": int(user.id), "tid": tenant_id, "sid": site_id},
    )
    db.commit()
    return user


def _login_json(client, email: str, password: str):
    resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _make_user_must_change(db, *, email: str, password: str, role: str, tenant_id: int, site_id: str) -> User:
    user = _seed_user(db, email=email, password=password, role=role, tenant_id=tenant_id, site_id=site_id)
    user.must_change_password = True
    db.commit()
    return user


def test_admin_reset_invalidates_all_prior_credentials():
    app = _make_app()
    with app.app_context():
        db = get_session()
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Tenant A")
            db.add(tenant)
            db.flush()
        site = Site(id="site-auth-version", name="Auth Version Site", tenant_id=tenant.id)
        db.add(site)
        db.flush()
        user_a = _seed_user(
            db,
            email="user.a@example.com",
            password="OldPassw0rd!",
            role="admin",
            tenant_id=tenant.id,
            site_id=site.id,
        )
        user_b = _seed_user(
            db,
            email="user.b@example.com",
            password="OtherPassw0rd!",
            role="admin",
            tenant_id=tenant.id,
            site_id=site.id,
        )
        admin = User(
            tenant_id=tenant.id,
            email="super@example.com",
            username="super@example.com",
            password_hash=generate_password_hash("SuperPassw0rd!"),
            role="superuser",
            full_name="Super User",
        )
        db.add(admin)
        db.commit()
        admin_id = admin.id
        user_a_id = user_a.id
        user_b_id = user_b.id
        db.close()

        client_a = app.test_client()
        client_admin = app.test_client()

        a_login = _login_json(client_a, "user.a@example.com", "OldPassw0rd!")
        access_a = a_login["access_token"]
        refresh_a = a_login["refresh_token"]
        with client_a.session_transaction() as sess:
            assert sess.get("auth_version") == 1

        _login_json(client_admin, "super@example.com", "SuperPassw0rd!")
        csrf = _csrf_from_html(client_admin.get("/ui/admin/users").data.decode("utf-8"))
        reset_resp = client_admin.post(
            f"/ui/admin/users/{user_a_id}/reset-password",
            data={"new_password": "NewPassw0rd!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert reset_resp.status_code == 200
        match = re.search(r"Tillfälligt lösenord skapat för .*?: ([^<\s]+)", reset_resp.data.decode("utf-8"))
        assert match is not None, reset_resp.data.decode("utf-8")
        temp_password = match.group(1)

        db = get_session()
        try:
            row = db.execute(
                text("SELECT password_hash, auth_version, refresh_token_jti, must_change_password FROM users WHERE id=:uid"),
                {"uid": user_a_id},
            ).fetchone()
            assert row is not None
            assert int(row[1]) == 2
            assert row[2] is None
            assert int(row[3]) == 1
        finally:
            db.close()

        assert client_a.get("/auth/me").status_code == 401
        assert client_a.get("/ui/account", follow_redirects=False).status_code in (301, 302, 401)

        bearer_me = client_a.get("/auth/me", headers={"Authorization": f"Bearer {access_a}"})
        assert bearer_me.status_code == 401
        assert (bearer_me.get_json() or {}).get("error") == "authentication required"

        refresh_resp = client_a.post("/auth/refresh", json={"refresh_token": refresh_a})
        assert refresh_resp.status_code == 401
        assert (refresh_resp.get_json() or {}).get("error") == "invalid token"

        old_login = client_a.post(
            "/auth/login",
            json={"email": "user.a@example.com", "password": "OldPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert old_login.status_code == 401
        new_login = client_a.post(
            "/auth/login",
            json={"email": "user.a@example.com", "password": temp_password},
            headers={"Accept": "application/json"},
        )
        assert new_login.status_code == 200
        assert (new_login.get_json() or {}).get("must_change_password") is True
        with client_a.session_transaction() as sess:
            assert sess.get("must_change_password") is True

        client_b = app.test_client()
        other_login = client_b.post(
            "/auth/login",
            json={"email": "user.b@example.com", "password": "OtherPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert other_login.status_code == 200


def test_self_service_change_clears_session_and_invalidates_old_credentials():
    app = _make_app()
    with app.app_context():
        db = get_session()
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Tenant A")
            db.add(tenant)
            db.flush()
        site = Site(id="site-auth-version", name="Auth Version Site", tenant_id=tenant.id)
        db.add(site)
        db.flush()
        user = _seed_user(
            db,
            email="user.self@example.com",
            password="OldPassw0rd!",
            role="admin",
            tenant_id=tenant.id,
            site_id=site.id,
        )
        user_id = user.id
        db.close()

        client = app.test_client()
        login = _login_json(client, "user.self@example.com", "OldPassw0rd!")
        access = login["access_token"]
        refresh = login["refresh_token"]
        csrf = _csrf_from_html(client.get("/ui/account").data.decode("utf-8"))

        change_resp = client.post(
            "/ui/account/password",
            data={
                "current_password": "OldPassw0rd!",
                "new_password": "NewPassw0rd!",
                "confirm_password": "NewPassw0rd!",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert change_resp.status_code == 200

        with client.session_transaction() as sess:
            assert sess.get("user_id") is None
            assert sess.get("auth_version") is None

        db = get_session()
        try:
            row = db.execute(
                text("SELECT password_hash, auth_version, refresh_token_jti, must_change_password FROM users WHERE id=:uid"),
                {"uid": user_id},
            ).fetchone()
            assert row is not None
            assert int(row[1]) == 2
            assert row[2] is None
            assert int(row[3]) == 0
        finally:
            db.close()

        relogin = client.post(
            "/auth/login",
            json={"email": "user.self@example.com", "password": "NewPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert relogin.status_code == 200
        assert (relogin.get_json() or {}).get("must_change_password") is False

        assert client.get("/auth/me", headers={"Authorization": f"Bearer {access}"}).status_code == 401
        assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401
        assert client.post(
            "/auth/login",
            json={"email": "user.self@example.com", "password": "OldPassw0rd!"},
            headers={"Accept": "application/json"},
        ).status_code == 401
        assert client.post(
            "/auth/login",
            json={"email": "user.self@example.com", "password": "NewPassw0rd!"},
            headers={"Accept": "application/json"},
        ).status_code == 200


def test_logout_clears_browser_session_and_refresh_jti():
    app = _make_app()
    with app.app_context():
        db = get_session()
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Tenant A")
            db.add(tenant)
            db.flush()
        site = Site(id="site-auth-version", name="Auth Version Site", tenant_id=tenant.id)
        db.add(site)
        db.flush()
        user = _seed_user(
            db,
            email="user.logout@example.com",
            password="LogoutPassw0rd!",
            role="admin",
            tenant_id=tenant.id,
            site_id=site.id,
        )
        user_id = user.id
        db.close()

        client = app.test_client()
        login = _login_json(client, "user.logout@example.com", "LogoutPassw0rd!")
        refresh = login["refresh_token"]
        csrf = _csrf_from_html(client.get("/ui/account").data.decode("utf-8"))
        logout_resp = client.post(
            "/ui/logout",
            data={"refresh_token": refresh, "csrf_token": csrf},
            follow_redirects=False,
        )
        assert logout_resp.status_code in (301, 302)

        with client.session_transaction() as sess:
            assert sess.get("user_id") is None
            assert sess.get("auth_version") is None

        db = get_session()
        try:
            row = db.execute(
                text("SELECT refresh_token_jti, auth_version FROM users WHERE id=:uid"),
                {"uid": user_id},
            ).fetchone()
            assert row is not None
            assert row[0] is None
            assert int(row[1]) == 1
        finally:
            db.close()

        assert client.get("/ui/account", follow_redirects=False).status_code in (301, 302, 401)
        assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401


@pytest.mark.parametrize(
    ("role", "blocked_path"),
    [
        ("unit_portal", "/ui/portal/week"),
        ("kitchen", "/ui/kitchen"),
        ("cook", "/ui/kitchen"),
        ("admin", "/ui/admin"),
    ],
)
def test_forced_change_blocks_role_app_routes(monkeypatch, role, blocked_path):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_app()
    with app.app_context():
        db = get_session()
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Tenant A")
            db.add(tenant)
            db.flush()
        site = Site(id=f"site-{role}-{uuid.uuid4().hex[:6]}", name=f"Site {role}", tenant_id=tenant.id)
        db.add(site)
        db.flush()
        email = f"{role}.forced.{uuid.uuid4().hex[:8]}@example.com"
        _make_user_must_change(db, email=email, password="TempPassw0rd!", role=role, tenant_id=tenant.id, site_id=site.id)
        client = app.test_client()

        login = client.post(
            "/auth/login",
            json={"email": email, "password": "TempPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login.status_code == 200
        assert (login.get_json() or {}).get("must_change_password") is True

        blocked = client.get(blocked_path, follow_redirects=False)
        assert blocked.status_code in (301, 302)
        assert "/ui/account" in (blocked.headers.get("Location") or "")

        account = client.get("/ui/account")
        assert account.status_code == 200
        body = account.data.decode("utf-8")
        assert "Du måste byta lösenord innan du fortsätter." in body
        assert "/ui/account/password" in body
        assert "app-shell__nav" not in body
        assert "Mitt konto" not in body

        logout = client.post("/ui/logout", follow_redirects=False)
        assert logout.status_code in (301, 302)
        with client.session_transaction() as sess:
            assert sess.get("user_id") is None
    db.close()


def test_forced_change_blocks_protected_json_api(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_app()
    with app.app_context():
        db = get_session()
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Tenant A")
            db.add(tenant)
            db.flush()
        site = Site(id=f"site-api-{uuid.uuid4().hex[:6]}", name="API Site", tenant_id=tenant.id)
        db.add(site)
        db.flush()
        email = f"api.forced.{uuid.uuid4().hex[:8]}@example.com"
        _make_user_must_change(db, email=email, password="TempPassw0rd!", role="admin", tenant_id=tenant.id, site_id=site.id)
        client = app.test_client()

        login = client.post(
            "/auth/login",
            json={"email": email, "password": "TempPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login.status_code == 200

        api_resp = client.get("/admin/tenants")
        assert api_resp.status_code == 401
        body = api_resp.get_json() or {}
        assert body.get("detail") == "authentication required"
        assert body.get("title") == "Unauthorized"

        me_resp = client.get("/auth/me")
        assert me_resp.status_code == 401
    db.close()


def test_systemadmin_reset_forces_password_change_and_bumps_auth_version(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_app()
    with app.app_context():
        db = get_session()
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Tenant A")
            db.add(tenant)
            db.flush()
        site = Site(id=f"site-sys-{uuid.uuid4().hex[:6]}", name="Sys Site", tenant_id=tenant.id)
        db.add(site)
        db.flush()
        tenant_id = tenant.id
        site_id = site.id
        admin_user = _seed_user(
            db,
            email=f"siteadmin.{uuid.uuid4().hex[:8]}@example.com",
            password="OldPassw0rd!",
            role="admin",
            tenant_id=tenant.id,
            site_id=site.id,
        )
        admin_user.must_change_password = False
        db.commit()
        admin_id = admin_user.id
        admin_email = admin_user.email
        super_user = User(
            tenant_id=tenant.id,
            email=f"super.{uuid.uuid4().hex[:8]}@example.com",
            username=f"super.{uuid.uuid4().hex[:8]}@example.com",
            password_hash=generate_password_hash("SuperPassw0rd!"),
            role="superuser",
            full_name="Super User",
        )
        db.add(super_user)
        db.commit()
        super_email = super_user.email
        db.close()

        client = app.test_client()
        login = client.post(
            "/auth/login",
            json={"email": super_email, "password": "SuperPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login.status_code == 200
        csrf = _csrf_from_html(client.get(f"/ui/systemadmin/customers/{tenant_id}/sites").data.decode("utf-8"))
        reset_resp = client.post(
            f"/ui/systemadmin/customers/{tenant_id}/sites/{site_id}/admins/{admin_id}/reset-password",
            data={"new_password": "ResetPassw0rd!", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert reset_resp.status_code in (301, 302)

        db = get_session()
        try:
            row = db.execute(
                text("SELECT auth_version, refresh_token_jti, must_change_password FROM users WHERE id=:uid"),
                {"uid": admin_id},
            ).fetchone()
            assert row is not None
            assert int(row[0]) == 2
            assert row[1] is None
            assert int(row[2]) == 1
        finally:
            db.close()

        relogin = client.post(
            "/auth/login",
            json={"email": admin_email, "password": "ResetPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert relogin.status_code == 200
        assert (relogin.get_json() or {}).get("must_change_password") is True


def test_unit_portal_canonical_department_portal_blocked_until_password_change(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_app()
    with app.app_context():
        db = get_session()
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Tenant A")
            db.add(tenant)
            db.flush()
        site = Site(id=f"portal-site-{uuid.uuid4().hex[:6]}", name="Portal Site", tenant_id=tenant.id)
        db.add(site)
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS departments("
                "id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT, notes TEXT NULL, resident_count_mode TEXT NOT NULL DEFAULT 'manual'"
                ")"
            )
        )
        dept_id = f"dept-{uuid.uuid4().hex[:8]}"
        db.execute(
            text(
                "INSERT OR REPLACE INTO departments(id, site_id, name, notes, resident_count_mode) "
                "VALUES(:id, :site_id, :name, '', 'manual')"
            ),
            {"id": dept_id, "site_id": site.id, "name": "Dept Portal"},
        )
        db.commit()

        user = User(
            tenant_id=tenant.id,
            email=f"unit.portal.{uuid.uuid4().hex[:8]}@example.com",
            username=f"unit.portal.{uuid.uuid4().hex[:8]}@example.com",
            password_hash=generate_password_hash("TempPassw0rd!"),
            role="unit_portal",
            department_id=dept_id,
            full_name="Unit Portal",
            must_change_password=True,
        )
        db.add(user)
        db.commit()
        email = user.email
        db.close()

        client = app.test_client()
        login = client.post(
            "/auth/login",
            json={"email": email, "password": "TempPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login.status_code == 200
        assert (login.get_json() or {}).get("must_change_password") is True

        blocked = client.get("/ui/portal/department/week?year=2026&week=40", follow_redirects=False)
        assert blocked.status_code in (301, 302)
        assert "/ui/account" in (blocked.headers.get("Location") or "")
        account = client.get("/ui/account")
        assert account.status_code == 200
        assert "Du måste byta lösenord innan du fortsätter." in account.get_data(as_text=True)

        csrf = _csrf_from_html(account.get_data(as_text=True))
        change = client.post(
            "/ui/account/password",
            data={
                "current_password": "TempPassw0rd!",
                "new_password": "NewPassw0rd!",
                "confirm_password": "NewPassw0rd!",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert change.status_code == 200

        relogin = client.post(
            "/auth/login",
            json={"email": email, "password": "NewPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert relogin.status_code == 200
        assert (relogin.get_json() or {}).get("must_change_password") is False

        portal = client.get("/ui/portal/department/week?year=2026&week=40")
        assert portal.status_code == 200
        html = portal.get_data(as_text=True)
        assert "Vecka 40" in html
