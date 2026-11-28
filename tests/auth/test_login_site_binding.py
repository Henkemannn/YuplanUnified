import uuid
from datetime import datetime, timezone

import pytest
from core.app_factory import create_app
from core.db import get_session, create_all
from core.models import User, Tenant, Site, Department, DietaryType
from core.jwt_utils import decode as jwt_decode
from werkzeug.security import generate_password_hash
from sqlalchemy import text


def _seed_tenant_and_user(db, role: str = "admin"):
    t = db.query(Tenant).first()
    if not t:
        t = Tenant(name="Primary")
        db.add(t)
        db.flush()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    u = User(tenant_id=t.id, email=email.lower(), username=email.lower(), password_hash=generate_password_hash("Passw0rd!"), role=role)
    db.add(u)
    db.commit()
    return email


def _seed_sites(db, count: int = 2):
    # Minimal sites table for tests
    db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL, tenant_id INTEGER, version INTEGER)"))
    for i in range(count):
        sid = f"site-{i+1}-{uuid.uuid4()}"
        db.execute(text("INSERT OR IGNORE INTO sites(id,name,tenant_id,version) VALUES(:i,:n,1,0)"), {"i": sid, "n": f"Site {i+1}"})
    db.commit()


def _seed_single_site(db, tenant_id: int) -> str:
    site_id = f"site-{uuid.uuid4()}"
    db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL, tenant_id INTEGER, version INTEGER)"))
    db.execute(
        text("INSERT OR REPLACE INTO sites(id,name,tenant_id,version) VALUES(:id,:name,:tid,0)"),
        {"id": site_id, "name": "Primary Site", "tid": tenant_id},
    )
    db.commit()
    return site_id


def _seed_user_with_email(db, *, email: str, role: str = "superuser", password: str = "Passw0rd!") -> int:
    t = db.query(Tenant).first()
    if not t:
        t = Tenant(name="Primary")
        db.add(t)
        db.flush()
    user = User(
        tenant_id=t.id,
        email=email,
        username=email.lower(),
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.add(user)
    db.commit()
    return user.id


def _set_account_state(db, *, email: str, is_active: bool | None = None, deleted: bool = False) -> None:
    user = db.query(User).filter(User.email == email.lower()).first()
    assert user is not None
    if is_active is not None:
        user.is_active = is_active
    if deleted:
        user.deleted_at = datetime.now(timezone.utc)
    db.commit()


def _seed_html_login_user(db, *, role: str, password: str = "Passw0rd!") -> tuple[str, str, str | None]:
    t = db.query(Tenant).first()
    if not t:
        t = Tenant(name="Primary")
        db.add(t)
        db.flush()
    site = Site(id=f"site-{uuid.uuid4().hex}", name="Primary Site", tenant_id=t.id)
    db.add(site)
    db.flush()
    department_id = None
    if role == "unit_portal":
        department_id = f"dept-{uuid.uuid4().hex}"
        dept = Department(
            id=department_id,
            site_id=site.id,
            name="Portal Dept",
            resident_count_mode="manual",
        )
        db.add(dept)
        db.flush()
    email = f"{role}.{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        tenant_id=t.id,
        email=email.lower(),
        username=email.lower(),
        password_hash=generate_password_hash(password),
        role=role,
        department_id=department_id,
    )
    db.add(user)
    db.flush()
    if role != "superuser":
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER PRIMARY KEY, "
                "tenant_id INTEGER NOT NULL, "
                "site_id TEXT NOT NULL)"
            )
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (:uid, :tid, :sid)"
            ),
            {"uid": int(user.id), "tid": int(t.id), "sid": site.id},
        )
    db.commit()
    return email.lower(), site.id, department_id


def _make_isolated_app():
    import os as _os
    import tempfile as _tf
    db_fd, db_path = _tf.mkstemp(prefix="login_bind_", suffix=".db")
    _os.close(db_fd)
    url = f"sqlite:///{db_path}"
    app = create_app({"TESTING": True, "database_url": url, "FORCE_DB_REINIT": True})
    with app.app_context():
        create_all()
    return app


def test_login_admin_json_forbidden_without_site_binding(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email = _seed_tenant_and_user(db, role="admin")
        _seed_sites(db, count=2)  # multiple sites -> cannot auto-bind
        c = app.test_client()
        r = c.post("/auth/login", json={"email": email, "password": "Passw0rd!"}, headers={"Accept": "application/json"})
        assert r.status_code == 403
        j = r.get_json() or {}
        assert j.get("error") == "forbidden"
        assert j.get("message") == "site_binding_required"
        assert "access_token" not in j
        assert "refresh_token" not in j
        with c.session_transaction() as sess:
            assert sess.get("user_id") is None
        assert c.get("/auth/me").status_code == 401


def test_login_admin_form_forbidden_without_site_binding(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email = _seed_tenant_and_user(db, role="admin")
        _seed_sites(db, count=2)
        c = app.test_client()
        r = c.post("/auth/login", data={"email": email, "password": "Passw0rd!"}, headers={"Accept": "text/html"}, follow_redirects=False)
        assert r.status_code == 403
        body = r.data.decode("utf-8")
        assert "Åtkomst nekad" in body
        with c.session_transaction() as sess:
            assert sess.get("user_id") is None
        assert c.get("/auth/me").status_code == 401


def test_login_admin_json_ok_with_kitchen_user_sites_binding(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        from sqlalchemy import text

        db = get_session()
        email = _seed_tenant_and_user(db, role="admin")
        _seed_sites(db, count=2)  # multiple sites -> explicit mapping is required

        sid_row = db.execute(text("SELECT id FROM sites ORDER BY id LIMIT 1")).fetchone()
        user_row = db.execute(text("SELECT id, tenant_id FROM users WHERE email=:e LIMIT 1"), {"e": email}).fetchone()
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                "PRIMARY KEY (user_id, site_id))"
            )
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (:uid, :tid, :sid)"
            ),
            {"uid": int(user_row[0]), "tid": int(user_row[1]), "sid": str(sid_row[0])},
        )
        db.commit()

        c = app.test_client()
        r = c.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        j = r.get_json() or {}
        assert j.get("ok") is True
        with c.session_transaction() as sess:
            assert (sess.get("site_id") or "").strip() == str(sid_row[0])


def test_legacy_user_site_binding_authorizes_session_and_bearer_paths(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email = _seed_tenant_and_user(db, role="admin")
        site_id = _seed_single_site(db, tenant_id=1)
        db.execute(text("ALTER TABLE users ADD COLUMN site_id TEXT"))
        user = db.query(User).filter(User.email == email).one()
        db.execute(
            text("UPDATE users SET site_id=:site_id WHERE id=:user_id"),
            {"site_id": site_id, "user_id": int(user.id)},
        )
        db.commit()

        client = app.test_client()
        login = client.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login.status_code == 200
        access_token = login.get_json()["access_token"]

        with client.session_transaction() as sess:
            assert sess.get("site_id") == site_id

        assert client.get("/ui/admin/specialkost").status_code == 200
        bearer = client.get(
            "/export/notes.csv",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert bearer.status_code == 200


def test_login_admin_ignores_stale_session_site_from_previous_user(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email = _seed_tenant_and_user(db, role="admin")
        _seed_sites(db, count=2)

        c = app.test_client()
        with c.session_transaction() as sess:
            sess["site_id"] = "stale-site-id"
            sess["site_lock"] = True

        r = c.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 403
        j = r.get_json() or {}
        assert j.get("error") == "forbidden"
        assert j.get("message") == "site_binding_required"
        with c.session_transaction() as sess:
            assert not (sess.get("site_id") or "").strip()


def test_login_replaces_display_identity_in_same_session(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        cook_email = "cook.a@yuplan.local"
        superuser_email = "henrik.jonsson@yuplan.se"
        t = db.query(Tenant).first()
        if not t:
            t = Tenant(name="Primary")
            db.add(t)
            db.flush()
        tenant_id = t.id
        cook_user = User(
            tenant_id=tenant_id,
            email=cook_email,
            username=cook_email,
            password_hash=generate_password_hash("CookPassw0rd!"),
            role="cook",
            full_name="Yuplan Cook A",
        )
        superuser_user = User(
            tenant_id=t.id,
            email=superuser_email,
            username=superuser_email,
            password_hash=generate_password_hash("HenrikPassw0rd!"),
            role="superuser",
            full_name=None,
        )
        db.add(cook_user)
        db.add(superuser_user)
        db.flush()
        cook_user_id = cook_user.id
        superuser_user_id = superuser_user.id
        db.commit()

        site_id = _seed_single_site(db, tenant_id=tenant_id)
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER PRIMARY KEY, "
                "tenant_id INTEGER NOT NULL, "
                "site_id TEXT NOT NULL)"
            )
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (:uid, :tid, :sid)"
            ),
            {"uid": int(cook_user_id), "tid": int(tenant_id), "sid": site_id},
        )
        db.commit()
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["site_id"] = site_id

        first = c.post(
            "/auth/login",
            json={"email": cook_email, "password": "CookPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert first.status_code == 200
        with c.session_transaction() as sess:
            assert sess.get("user_id") == cook_user_id
            assert sess.get("role") == "cook"
            assert sess.get("full_name") == "Yuplan Cook A"
            assert sess.get("user_email") == cook_email
            assert sess.get("username") == cook_email

        second = c.post(
            "/auth/login",
            json={"email": superuser_email, "password": "HenrikPassw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert second.status_code == 200
        with c.session_transaction() as sess:
            assert sess.get("user_id") == superuser_user_id
            assert sess.get("role") == "superuser"
            assert sess.get("user_email") == superuser_email
            assert sess.get("username") == superuser_email
            assert sess.get("full_name") is None

        page = c.get("/ui/admin/dashboard")
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert "Yuplan Cook A (superuser)" not in html


@pytest.mark.parametrize(
    ("role", "expected_target"),
    [
        ("unit_portal", "/ui/portal/department"),
        ("staff", "/ui/portal/week"),
        ("department", "/ui/portal/week"),
        ("admin", "/ui/admin"),
        ("kitchen", "/ui/kitchen"),
        ("superuser", "/ui/systemadmin/dashboard"),
    ],
)
def test_login_html_lands_roles_on_expected_target(monkeypatch, role, expected_target):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        try:
            email, _, _ = _seed_html_login_user(db, role=role, password="RolePassw0rd!")
            c = app.test_client()
            resp = c.post(
                "/auth/login",
                data={"email": email, "password": "RolePassw0rd!"},
                headers={"Accept": "text/html"},
                follow_redirects=False,
            )
            assert resp.status_code in (301, 302)
            assert expected_target in (resp.headers.get("Location") or "")
        finally:
            db.close()


def test_refresh_token_is_not_accepted_as_bearer_on_both_authz_paths(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email = _seed_tenant_and_user(db, role="admin")
        user = db.query(User).filter(User.email == email.lower()).one()
        site_id = _seed_single_site(db, tenant_id=int(user.tenant_id))
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                "PRIMARY KEY (user_id, site_id))"
            )
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (:uid, :tid, :sid)"
            ),
            {"uid": int(user.id), "tid": int(user.tenant_id), "sid": site_id},
        )
        db.commit()
        client = app.test_client()

        login_response = client.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login_response.status_code == 200
        tokens = login_response.get_json()
        assert tokens is not None
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        assert client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code == 200
        assert client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        ).status_code == 401

        assert client.post(
            "/api/kitchen/planering/normal_exclusions/toggle",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code == 400
        assert client.post(
            "/api/kitchen/planering/normal_exclusions/toggle",
            json={},
            headers={"Authorization": f"Bearer {refresh_token}"},
        ).status_code == 401

        assert client.get(
            "/admin/stats",
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code == 200
        assert client.get(
            "/admin/stats",
            headers={"Authorization": f"Bearer {refresh_token}"},
        ).status_code == 401
        db.close()


def test_revoked_user_access_token_session_and_refresh_are_rejected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email = _seed_tenant_and_user(db, role="superuser")
        client = app.test_client()
        login_response = client.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login_response.status_code == 200
        tokens = login_response.get_json()
        assert tokens is not None
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        user = db.query(User).filter(User.email == email.lower()).one()
        user_id = int(user.id)

        db.execute(text("UPDATE users SET is_active = 0 WHERE id = :uid"), {"uid": user_id})
        db.commit()

        session_response = client.post(
            "/api/kitchen/planering/normal_exclusions/toggle",
            json={},
        )
        assert session_response.status_code == 401
        bearer_response = client.post(
            "/api/kitchen/planering/normal_exclusions/toggle",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert bearer_response.status_code == 401
        refresh_response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 401

        db.execute(
            text(
                "UPDATE users SET is_active = 1, auth_version = auth_version + 1 "
                "WHERE id = :uid"
            ),
            {"uid": user_id},
        )
        db.commit()
        old_access_response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert old_access_response.status_code == 401
        old_refresh_response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert old_refresh_response.status_code == 401
        db.close()


def test_current_site_binding_and_role_tenant_changes_revoke_old_context(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email = _seed_tenant_and_user(db, role="admin")
        user = db.query(User).filter(User.email == email.lower()).one()
        site_id = _seed_single_site(db, tenant_id=int(user.tenant_id))
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                "PRIMARY KEY (user_id, site_id))"
            )
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (:uid, :tid, :sid)"
            ),
            {"uid": int(user.id), "tid": int(user.tenant_id), "sid": site_id},
        )
        db.commit()
        client = app.test_client()
        login_response = client.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login_response.status_code == 200
        access_token = login_response.get_json()["access_token"]

        db.execute(
            text(
                "DELETE FROM kitchen_user_sites "
                "WHERE user_id=:uid AND tenant_id=:tid AND site_id=:sid"
            ),
            {"uid": int(user.id), "tid": int(user.tenant_id), "sid": site_id},
        )
        db.commit()
        assert client.get(
            "/admin/audit",
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code == 401

        db.execute(
            text("INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) VALUES (:uid, :tid, :sid)"),
            {"uid": int(user.id), "tid": int(user.tenant_id), "sid": site_id},
        )
        db.execute(text("UPDATE users SET role = 'cook' WHERE id = :uid"), {"uid": int(user.id)})
        db.commit()
        with client.session_transaction() as sess:
            sess["site_id"] = site_id
            sess["tenant_id"] = int(user.tenant_id)
        assert client.get(
            "/admin/audit",
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code == 403

        tenant = Tenant(name=f"Replacement {uuid.uuid4().hex}")
        db.add(tenant)
        db.flush()
        db.execute(
            text("UPDATE users SET tenant_id = :tenant_id WHERE id = :uid"),
            {"tenant_id": int(tenant.id), "uid": int(user.id)},
        )
        db.commit()
        assert client.get(
            "/admin/audit",
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code == 401
        db.close()


def test_stateless_bearer_uses_current_db_site_binding(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email, site_id, _ = _seed_html_login_user(db, role="admin")
        user = db.query(User).filter(User.email == email.lower()).one()
        user_id = int(user.id)
        tenant_id = int(user.tenant_id)
        diet = DietaryType(
            tenant_id=tenant_id,
            site_id=site_id,
            name="Synthetic exclusion diet",
        )
        db.add(diet)
        db.flush()
        diet_id = int(diet.id)
        db.commit()
        login_client = app.test_client()
        login_response = login_client.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login_response.status_code == 200
        access_token = login_response.get_json()["access_token"]

        stateless_core_client = app.test_client()
        core_payload = {
            "site_id": site_id,
            "year": 2026,
            "week": 6,
            "day_index": 2,
            "meal": "lunch",
            "alt": "1",
            "diet_type_id": str(diet_id),
        }
        core_response = stateless_core_client.post(
            "/api/kitchen/planering/normal_exclusions/toggle",
            json=core_payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert core_response.status_code == 200, core_response.get_data(as_text=True)

        stateless_app_client = app.test_client()
        app_response = stateless_app_client.get(
            f"/admin/stats?site_id={site_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert app_response.status_code == 200, app_response.get_data(as_text=True)

        site_b = _seed_single_site(db, tenant_id=1)
        denied_payload = dict(core_payload, site_id=site_b)
        denied_core = app.test_client().post(
            "/api/kitchen/planering/normal_exclusions/toggle",
            json=denied_payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert denied_core.status_code in (401, 403)

        db.execute(
            text(
                "DELETE FROM kitchen_user_sites "
                "WHERE user_id=:uid AND tenant_id=:tid AND site_id=:sid"
            ),
            {"uid": user_id, "tid": tenant_id, "sid": site_id},
        )
        db.commit()
        revoked_payload = dict(core_payload)
        revoked = app.test_client().post(
            "/api/kitchen/planering/normal_exclusions/toggle",
            json=revoked_payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert revoked.status_code == 401
        db.close()


@pytest.mark.parametrize("account_state", ("inactive", "deleted"))
def test_refresh_rejects_inactive_or_deleted_user(monkeypatch, account_state):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        email, site_id, _ = _seed_html_login_user(db, role="admin")
        c = app.test_client()
        login_response = c.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            headers={"Accept": "application/json"},
        )
        assert login_response.status_code == 200, login_response.get_json()
        refresh_token = login_response.get_json()["refresh_token"]
        refresh_payload = jwt_decode(refresh_token, secret=app.config["JWT_SECRET"])
        assert refresh_payload["auth_version"] == 1
        if account_state == "inactive":
            _set_account_state(db, email=email, is_active=False)
        else:
            _set_account_state(db, email=email, deleted=True)

        refresh_response = c.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )
        assert refresh_response.status_code == 401
        body = refresh_response.get_json() or {}
        assert body.get("error") == "invalid token"
        assert body.get("message") == "invalid token"


def test_login_unit_portal_follow_redirect_reaches_department_portal(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        try:
            email, _, department_id = _seed_html_login_user(db, role="unit_portal", password="PortalPassw0rd!")
            assert department_id is not None
            c = app.test_client()
            resp = c.post(
                "/auth/login",
                data={"email": email, "password": "PortalPassw0rd!"},
                headers={"Accept": "text/html"},
                follow_redirects=False,
            )
            assert resp.status_code in (301, 302)
            assert (resp.headers.get("Location") or "").endswith("/ui/portal/department")

            follow = c.post(
                "/auth/login",
                data={"email": email, "password": "PortalPassw0rd!"},
                headers={"Accept": "text/html"},
                follow_redirects=True,
            )
            assert follow.status_code == 200
            assert follow.request.path == "/ui/portal/department"
            html = follow.get_data(as_text=True)
            assert "Avdelningsportal" in html
            assert 'href="/ui/portal/department/week' in html
            assert "Veckonavigering" in html
        finally:
            db.close()


def test_login_unit_portal_missing_department_binding_is_denied(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        try:
            t = db.query(Tenant).first()
            if not t:
                t = Tenant(name="Primary")
                db.add(t)
                db.flush()
            site = Site(id=f"site-{uuid.uuid4().hex}", name="Primary Site", tenant_id=t.id)
            db.add(site)
            db.flush()
            email = f"unit_portal.{uuid.uuid4().hex[:8]}@example.com"
            user = User(
                tenant_id=t.id,
                email=email.lower(),
                username=email.lower(),
                password_hash=generate_password_hash("PortalPassw0rd!"),
                role="unit_portal",
                department_id=None,
            )
            db.add(user)
            db.commit()

            c = app.test_client()
            resp = c.post(
                "/auth/login",
                data={"email": email.lower(), "password": "PortalPassw0rd!"},
                headers={"Accept": "text/html"},
                follow_redirects=False,
            )
            assert resp.status_code in (301, 302)
            location = resp.headers.get("Location") or ""
            assert "/ui/portal/department" in location

            next_resp = c.get(location)
            assert next_resp.status_code == 403
        finally:
            db.close()


def test_login_accepts_legacy_mixed_case_email(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        try:
            _seed_user_with_email(db, email="Legacy.Mixed@Example.Com", role="superuser", password="SuperPassw0rd!")
            c = app.test_client()
            r = c.post(
                "/auth/login",
                json={"email": "legacy.mixed@example.com", "password": "SuperPassw0rd!"},
                headers={"Accept": "application/json"},
            )
            assert r.status_code == 200
            j = r.get_json() or {}
            assert j.get("ok") is True
            with c.session_transaction() as sess:
                assert sess.get("user_email") == "Legacy.Mixed@Example.Com"
        finally:
            db.close()


def test_login_accepts_arbitrary_client_casing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        try:
            stored_email = _seed_tenant_and_user(db, role="superuser")
            c = app.test_client()
            client_email = stored_email.swapcase()
            r = c.post(
                "/auth/login",
                json={"email": client_email, "password": "Passw0rd!"},
                headers={"Accept": "application/json"},
            )
            assert r.status_code == 200
            j = r.get_json() or {}
            assert j.get("ok") is True
            with c.session_transaction() as sess:
                assert sess.get("user_id") is not None
                assert (sess.get("user_email") or "").lower() == stored_email.lower()

            row = db.execute(
                text("SELECT email FROM users WHERE email = :email LIMIT 1"),
                {"email": stored_email.lower()},
            ).fetchone()
            assert row is not None
            assert row[0] == stored_email.lower()
        finally:
            db.close()


def test_login_fails_closed_for_ambiguous_case_variants(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    app = _make_isolated_app()
    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash

            tenant = db.query(Tenant).first()
            if not tenant:
                tenant = Tenant(name="Primary")
                db.add(tenant)
                db.flush()

            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, username, password_hash, role, is_active) "
                    "VALUES (:tid, 'ambiguous@example.com', 'ambiguous_a', :ph, 'superuser', 1)"
                ),
                {"tid": tenant.id, "ph": generate_password_hash("Passw0rd!")},
            )
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, username, password_hash, role, is_active) "
                    "VALUES (:tid, 'Ambiguous@Example.com', 'ambiguous_b', :ph, 'superuser', 1)"
                ),
                {"tid": tenant.id, "ph": generate_password_hash("Passw0rd!")},
            )
            db.commit()

            c = app.test_client()
            r = c.post(
                "/auth/login",
                json={"email": "ambiguous@example.com", "password": "Passw0rd!"},
                headers={"Accept": "application/json"},
            )
            assert r.status_code == 401
            body = r.get_json() or {}
            assert body.get("error") == "invalid credentials"
            assert body.get("message") == "invalid credentials"

            with c.session_transaction() as sess:
                assert sess.get("user_id") is None
                assert sess.get("role") is None

            rows = db.execute(
                text("SELECT id, email FROM users WHERE lower(email) = 'ambiguous@example.com' ORDER BY id"),
            ).fetchall()
            assert len(rows) == 2
        finally:
            db.close()
