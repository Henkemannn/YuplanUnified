import time

from core.app_factory import create_app


def test_auth_rate_limit_basic(monkeypatch):
    cfg = {
        "TESTING": True,
        "SECRET_KEY": "x",
        "AUTH_RATE_LIMIT": {"window_sec": 60, "max_failures": 3, "lock_sec": 2},
    }
    app = create_app(cfg)
    client = app.test_client()

    # create a user manually in DB
    from werkzeug.security import generate_password_hash

    from core.db import get_session
    from core.models import Tenant, User

    db = get_session()
    import uuid

    t = Tenant(name="T1_" + uuid.uuid4().hex[:6])
    db.add(t)
    db.flush()
    user_email = f"u_{uuid.uuid4().hex[:6]}@example.com"
    u = User(
        tenant_id=t.id,
        email=user_email,
        password_hash=generate_password_hash("pw"),
        role="admin",
        unit_id=None,
    )
    db.add(u)
    db.commit()
    db.close()

    # 1st wrong
    r = client.post("/auth/login", json={"email": user_email, "password": "bad"})
    assert r.status_code == 401
    # 2nd wrong
    r = client.post("/auth/login", json={"email": user_email, "password": "bad"})
    assert r.status_code == 401
    # 3rd wrong -> lock (if not, print debug)
    r = client.post("/auth/login", json={"email": user_email, "password": "bad"})
    if r.status_code != 429:
        print("DEBUG body", r.get_json())
        print("DEBUG cfg", cfg)
        print("DEBUG app cfg", app.config.get("AUTH_RATE_LIMIT"))
    assert r.status_code == 429
    # Still locked for correct password
    r = client.post("/auth/login", json={"email": user_email, "password": "pw"})
    assert r.status_code == 429
    # wait lock_sec
    time.sleep(2.1)
    # Now should allow correct login
    # Seed session site binding to satisfy strict site policy
    with client.session_transaction() as sess:
        sess["site_id"] = "test-site"
    r = client.post("/auth/login", json={"email": user_email, "password": "pw"})
    assert r.status_code == 200
    assert r.is_json and r.get_json().get("ok") is True
