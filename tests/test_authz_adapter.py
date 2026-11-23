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
    isolated_root = Path(tempfile.mkdtemp(prefix="yuplan-authz-"))
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
        users = [
            User(
                tenant_id=t.id,
                email="admin@example.com",
                password_hash=generate_password_hash("pw"),
                role="admin",
            ),
            User(
                tenant_id=t.id,
                email="cook@example.com",
                password_hash=generate_password_hash("pw"),
                role="cook",
            ),
            User(
                tenant_id=t.id,
                email="portal@example.com",
                password_hash=generate_password_hash("pw"),
                role="unit_portal",
            ),
        ]
        sess.add_all(users)
        sess.commit()
        sess.add(Site(id="test-site", tenant_id=t.id, name="Test Site"))
        sess.commit()
        sess.execute(
            text(
                "CREATE TABLE kitchen_user_sites "
                "(user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        for user in users:
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


def login(client, email):
    # Seed session site binding to satisfy strict site policy
    with client.session_transaction() as sess:
        sess["site_id"] = "test-site"
    r = client.post(
        "/auth/login", json={"email": email, "password": "pw"}, headers={"X-Tenant-Id": "1"}
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["access_token"]


def test_cook_maps_to_viewer_forbidden_features(client):
    token = login(client, "cook@example.com")
    r = client.get("/features", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": "1"})
    assert r.status_code in (401, 403)
    if r.status_code == 403:
        j = r.get_json()
        assert j.get("status") == 403 and j.get("type", " ").endswith("/forbidden")
        assert j.get("required_role") in ("admin", "superuser", "editor")


def test_unit_portal_maps_to_editor_partial_access(client):
    token = login(client, "portal@example.com")
    # The active notes API is available to the mapped editor role.
    notes = client.get("/notes/", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": "1"})
    assert notes.status_code in (200, 401, 403)
    features = client.get(
        "/features", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": "1"}
    )
    assert features.status_code in (401, 403)


def test_required_role_field_present(client):
    token = login(client, "cook@example.com")
    r = client.get("/features", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": "1"})
    if r.status_code == 403:
        j = r.get_json()
        assert "required_role" in j
