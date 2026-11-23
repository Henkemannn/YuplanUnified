import gc
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session, init_engine
from core.models import Site, Task, Tenant, User
from core.tasks_service import update_task as service_update_task
from core.app_authz import AuthzError


@pytest.fixture()
def app(request):
    state = request.config._yuplan_test_db_state
    isolated_root = Path(tempfile.mkdtemp(prefix="yuplan-auth-rbac-"))
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
    # Direct metadata create (simpler than running full alembic chain for unit test scope)
    from core.models import Base

    sess = get_session()
    try:
        engine = sess.get_bind()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        # seed tenant and users
        t1 = Tenant(name="Tenant1")
        sess.add(t1)
        sess.commit()
        sess.refresh(t1)
        users = [
            User(
                tenant_id=t1.id,
                email="a@example.com",
                password_hash=generate_password_hash("pw"),
                role="cook",
            ),
            User(
                tenant_id=t1.id,
                email="b@example.com",
                password_hash=generate_password_hash("pw"),
                role="cook",
            ),
            User(
                tenant_id=t1.id,
                email="admin@example.com",
                password_hash=generate_password_hash("pw"),
                role="admin",
            ),
            User(
                tenant_id=t1.id,
                email="su@example.com",
                password_hash=generate_password_hash("pw"),
                role="superuser",
            ),
        ]
        sess.add_all(users)
        sess.commit()
        sess.add(Site(id="test-site", tenant_id=t1.id, name="Test Site"))
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
                {"uid": user.id, "tid": t1.id, "sid": "test-site"},
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


def login(client, email, password="pw", tenant_id=1):
    # Seed session site binding to satisfy strict site policy
    with client.session_transaction() as sess:
        sess["site_id"] = "test-site"
    res = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"X-Tenant-Id": str(tenant_id)},
    )
    assert res.status_code == 200, res.get_json()
    return res.get_json()


def test_auth_flow_and_unauthorized(client):
    # login userA
    data = login(client, "a@example.com")
    access = data["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    # missing token
    with client.session_transaction() as sess:
        sess.clear()
    r2 = client.get("/auth/me", headers={"X-Tenant-Id": "1"})
    assert r2.status_code == 401
    j = r2.get_json()
    assert j.get("error") == "authentication required"


def test_refresh_rotation(client):
    data = login(client, "a@example.com")
    refresh1 = data["refresh_token"]
    r = client.post("/auth/refresh", json={"refresh_token": refresh1}, headers={"X-Tenant-Id": "1"})
    assert r.status_code == 200
    pair2 = r.get_json()
    refresh2 = pair2["refresh_token"]
    # reuse first should now fail
    r_fail = client.post(
        "/auth/refresh", json={"refresh_token": refresh1}, headers={"X-Tenant-Id": "1"}
    )
    assert r_fail.status_code in (401, 403)
    j = r_fail.get_json()
    assert j["error"] in ("unauthorized", "forbidden", "invalid token")
    # second still works once more rotation
    r_ok = client.post(
        "/auth/refresh", json={"refresh_token": refresh2}, headers={"X-Tenant-Id": "1"}
    )
    assert r_ok.status_code == 200


def test_rbac_ownership_and_admin_override(client):
    db = get_session()
    try:
        users = {u.email: u.id for u in db.query(User).all()}
        task = Task(
            tenant_id=1,
            task_type="prep",
            title="Owned by A",
            creator_user_id=users["a@example.com"],
            status="todo",
            done=False,
        )
        db.add(task)
        db.commit()
        with pytest.raises(AuthzError):
            service_update_task(
                db,
                tenant_id=1,
                user_id=users["b@example.com"],
                role="cook",
                task_id=task.id,
                payload={"status": "doing"},
            )
        result = service_update_task(
            db,
            tenant_id=1,
            user_id=users["admin@example.com"],
            role="admin",
            task_id=task.id,
            payload={"status": "doing"},
        )
        assert result == {"ok": True, "updated": True}
    finally:
        db.close()


def test_rate_limits_active_features(client):
    # Login admin and exercise an active feature endpoint.
    d = login(client, "admin@example.com")
    access = d["access_token"]
    codes = []
    for _ in range(4):
        r = client.post(
            "/features/set",
            json={"name": f"inline_ui_{_}", "enabled": True},
            headers={
                "Authorization": f"Bearer {access}",
                "X-Tenant-Id": "1",
                "X-Force-Rate-Limit": "1",
            },
        )
        codes.append(r.status_code)
    assert 429 in codes


def test_error_shapes(client):
    # unauthorized
    r = client.get("/features", headers={"X-Tenant-Id": "1"})
    assert r.status_code == 401
    j = r.get_json()
    assert j.get("status") == 401 and j.get("type", " ").endswith("/unauthorized")
    viewer = login(client, "a@example.com")
    forb = client.get(
        "/features",
        headers={"Authorization": f"Bearer {viewer['access_token']}", "X-Tenant-Id": "1"},
    )
    assert forb.status_code == 403
    jf = forb.get_json()
    assert jf.get("status") == 403 and jf.get("type", " ").endswith("/forbidden")
    # Rate-limited shape on an active endpoint.
    a2 = login(client, "admin@example.com")
    # first call consumes 1, then hammer to exceed using forced tiny limit of 1
    client.post(
        "/features/set",
        json={"name": "rate_shape_priming", "enabled": True},
        headers={
            "Authorization": f"Bearer {a2['access_token']}",
            "X-Tenant-Id": "1",
            "X-Force-Rate-Limit": "1",
            "X-Force-Rate-Limit-Limit": "1",
        },
    )
    rl = client.post(
        "/features/set",
        json={"name": "rate_shape", "enabled": True},
        headers={
            "Authorization": f"Bearer {a2['access_token']}",
            "X-Tenant-Id": "1",
            "X-Force-Rate-Limit": "1",
            "X-Force-Rate-Limit-Limit": "1",
        },
    )
    assert rl.status_code == 429
    jr = rl.get_json()
    assert jr.get("status") == 429 and jr.get("type", " ").endswith("/rate_limited")


@pytest.mark.parametrize("account_state", ("inactive", "deleted"))
def test_deactivated_or_deleted_session_cannot_access_protected_routes(client, account_state):
    sess = get_session()
    try:
        tenant = sess.query(Tenant).first()
        email = f"stateful-{account_state}-{datetime.utcnow().timestamp():.0f}@example.com"
        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=generate_password_hash("pw"),
            role="admin",
        )
        sess.add(user)
        sess.commit()
        sess.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:uid, :tid, :sid)"
            ),
            {"uid": user.id, "tid": tenant.id, "sid": "test-site"},
        )
        sess.commit()

        login(client, email)

        if account_state == "inactive":
            sess.execute(text("UPDATE users SET is_active = 0 WHERE email = :email"), {"email": email})
        else:
            sess.execute(
                text("UPDATE users SET deleted_at = :deleted_at WHERE email = :email"),
                {"email": email, "deleted_at": datetime.now(timezone.utc)},
            )
        sess.commit()
        sess.expire_all()
    finally:
        sess.close()

    features = client.get("/features", headers={"X-Tenant-Id": "1"})
    assert features.status_code == 401
    features_body = features.get_json() or {}
    assert features_body.get("status") == 401
    assert features_body.get("type", " ").endswith("/unauthorized")

    me = client.get("/auth/me")
    assert me.status_code == 401
    me_body = me.get_json() or {}
    assert me_body.get("error") == "authentication required"
