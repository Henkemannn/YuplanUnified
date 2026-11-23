import gc
from pathlib import Path
import shutil
import tempfile

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session, init_engine
from core.models import Base, Site, Tenant, User


@pytest.fixture()
def app(request):
    state = request.config._yuplan_test_db_state
    isolated_root = Path(tempfile.mkdtemp(prefix="yuplan-pocket6-"))
    isolated_db = isolated_root / "main.db"
    isolated_builder_db = isolated_root / "builder.db"
    original_db_url = f"sqlite:///{state['main_db'].as_posix()}"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "JWT_SECRET": "secret",
            "database_url": f"sqlite:///{isolated_db.as_posix()}",
            "BUILDER_DB_PATH": str(isolated_builder_db),
            "FORCE_DB_REINIT": True,
        }
    )
    sess = get_session()
    try:
        engine = sess.get_bind()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        t = Tenant(name="T1")
        sess.add(t)
        sess.commit()
        sess.refresh(t)
        u_admin = User(
            tenant_id=t.id,
            email="admin@example.com",
            password_hash=generate_password_hash("pw"),
            role="admin",
        )
        u_view = User(
            tenant_id=t.id,
            email="view@example.com",
            password_hash=generate_password_hash("pw"),
            role="viewer",
        )
        sess.add_all([u_admin, u_view])
        sess.commit()
        sess.add(Site(id="test-site", tenant_id=t.id, name="Test Site"))
        sess.commit()
        sess.execute(
            text(
                "CREATE TABLE kitchen_user_sites "
                "(user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        for user in (u_admin, u_view):
            sess.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:uid, :tid, :sid)"
                ),
                {"uid": user.id, "tid": t.id, "sid": "test-site"},
            )
        sess.commit()
        yield app
    finally:
        sess.close()
        from core import db as db_mod

        if db_mod._SessionFactory is not None:
            db_mod._SessionFactory.remove()
        if db_mod._engine is not None:
            db_mod._engine.dispose(close=True)
        db_mod._SessionFactory = None
        db_mod._engine = None
        init_engine(original_db_url, force=True)
        gc.collect()
        shutil.rmtree(isolated_root)


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email: str):
    # Seed session site binding to satisfy strict site policy for non-superusers
    with client.session_transaction() as sess:
        sess["site_id"] = "test-site"
    r = client.post(
        "/auth/login", json={"email": email, "password": "pw"}, headers={"X-Tenant-Id": "1"}
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["access_token"]


def test_401_envelope(client):
    # Access protected endpoint without token -> unauthorized
    r = client.get("/features", headers={"X-Tenant-Id": "1"})
    assert r.status_code == 401
    j = r.get_json()
    assert j.get("type") and j.get("status") == 401, j
    assert j["type"].endswith("/unauthorized")


def test_session_login_and_access(client):
    token = login(client, "admin@example.com")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": "1"})
    assert r.status_code == 200


def test_403_role_mismatch(client):
    token = login(client, "view@example.com")
    # viewer tries to hit feature flags admin endpoint
    r = client.get("/features", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": "1"})
    # either 403 or (if role mapping changed) 401 fallback, assert forbidden envelope if 403
    if r.status_code == 403:
        j = r.get_json()
        assert j.get("status") == 403 and j.get("type", " ").endswith("/forbidden")
    else:
        assert r.status_code in (401, 403)


def test_404_not_found_resource(client):
    token = login(client, "admin@example.com")
    r = client.get(
        "/notes/999999", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": "1"}
    )
    assert r.status_code in (404, 403)  # if forbidden due to tenant mismatch logic
    if r.status_code == 404:
        j = r.get_json()
        assert j.get("status") == 404 and j.get("type", " ").endswith("/not_found")
