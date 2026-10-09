from __future__ import annotations

import os
import tempfile
import uuid
import re

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
                text("SELECT password_hash, auth_version, refresh_token_jti FROM users WHERE id=:uid"),
                {"uid": user_a_id},
            ).fetchone()
            assert row is not None
            assert int(row[1]) == 2
            assert row[2] is None
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

        other_login = client_a.post(
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
                text("SELECT password_hash, auth_version, refresh_token_jti FROM users WHERE id=:uid"),
                {"uid": user_id},
            ).fetchone()
            assert row is not None
            assert int(row[1]) == 2
            assert row[2] is None
        finally:
            db.close()

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
