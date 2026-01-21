import uuid
from core.app_factory import create_app
from core.db import get_session, create_all
from core.models import User, Tenant
from werkzeug.security import generate_password_hash


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
    from sqlalchemy import text
    # Minimal sites table for tests
    db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
    for i in range(count):
        sid = f"site-{i+1}-{uuid.uuid4()}"
        db.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES(:i,:n)"), {"i": sid, "n": f"Site {i+1}"})
    db.commit()


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
