import uuid
from core.app_factory import create_app
from core.db import get_session, create_all
from core.models import User, Tenant
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
