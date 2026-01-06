import os
import uuid
from core.app_factory import create_app
from core.db import get_session
from core.models import User, Tenant
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
