from __future__ import annotations

import pytest

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Tenant, User
from sqlalchemy import text


def _enable_admin(app):
    registry = app.feature_registry
    if not registry.has("ff.admin.enabled"):
        registry.add("ff.admin.enabled")
    registry.set("ff.admin.enabled", True)


def bind_test_user_to_site(app, site_id: str, *, user_id: int = 1, tenant_id: int = 1) -> None:
    """Create the explicit DB binding required by current authz tests."""
    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites "
                    "(user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, "
                    "site_id TEXT NOT NULL, PRIMARY KEY (user_id, site_id))"
                )
            )
            user = db.query(User).filter(User.id == user_id).first()
            if user is None:
                user = User(
                    id=user_id,
                    tenant_id=tenant_id,
                    username=f"admin-{user_id}",
                    email=f"admin-{user_id}@example.test",
                    password_hash="synthetic",
                    role="admin",
                    auth_version=1,
                    is_active=True,
                )
                db.add(user)
            else:
                user.tenant_id = tenant_id
                user.role = "admin"
                user.is_active = True
                user.deleted_at = None
                user.auth_version = 1
            db.flush()
            db.execute(
                text("DELETE FROM kitchen_user_sites WHERE user_id=:user_id"),
                {"user_id": user_id},
            )
            user_columns = {
                row[1] for row in db.execute(text("PRAGMA table_info('users')")).fetchall()
            }
            if "site_id" in user_columns:
                db.execute(
                    text("UPDATE users SET site_id=:site_id WHERE id=:user_id"),
                    {"site_id": site_id, "user_id": user_id},
                )
            if "department_id" in user_columns:
                db.execute(
                    text("UPDATE users SET department_id=NULL WHERE id=:user_id"),
                    {"user_id": user_id},
                )
            db.execute(
                text(
                    "INSERT OR IGNORE INTO sites (id, name, tenant_id, version) "
                    "VALUES (:site_id, :site_id, :tenant_id, 0)"
                ),
                {"site_id": site_id, "tenant_id": tenant_id},
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                    "VALUES (:user_id, :tenant_id, :site_id)"
                ),
                {"user_id": user_id, "tenant_id": tenant_id, "site_id": site_id},
            )
            db.commit()
            from core.admin_user_repo import _resolve_user_scope

            resolved_tenant, resolved_site, valid_scope = _resolve_user_scope(db, user_id)
            assert (resolved_tenant, resolved_site, valid_scope) == (
                tenant_id,
                site_id,
                True,
            )
            binding = db.execute(
                text(
                    "SELECT 1 FROM kitchen_user_sites "
                    "WHERE user_id=:user_id AND tenant_id=:tenant_id AND site_id=:site_id"
                ),
                {"user_id": user_id, "tenant_id": tenant_id, "site_id": site_id},
            ).fetchone()
            assert binding is not None
        finally:
            db.close()


def bind_current_test_site(app, client, *, user_id: int = 1, tenant_id: int = 1) -> str:
    with client.session_transaction() as current:
        site_id = str(current["site_id"])
    bind_test_user_to_site(app, site_id, user_id=user_id, tenant_id=tenant_id)
    return site_id


@pytest.fixture
def f01a_app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "database_url": f"sqlite:///{(tmp_path / 'f01a.db').as_posix()}",
        }
    )
    with app.app_context():
        create_all()
        db = get_session()
        try:
            tenant_a = Tenant(name="Tenant A")
            tenant_b = Tenant(name="Tenant B")
            db.add_all([tenant_a, tenant_b])
            db.flush()
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites "
                    "(user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, "
                    "site_id TEXT NOT NULL, PRIMARY KEY (user_id, site_id))"
                )
            )
            db.execute(
                text(
                    "INSERT INTO sites (id, name, tenant_id, version) VALUES "
                    "(:a, 'Site A', :ta, 0), (:b, 'Site B', :ta, 0), "
                    "(:c, 'Site C', :tb, 0)"
                ),
                {"a": "site-a", "b": "site-b", "c": "site-c", "ta": tenant_a.id, "tb": tenant_b.id},
            )
            db.execute(
                text(
                    "INSERT INTO departments "
                    "(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) "
                    "VALUES "
                    "('dept-a', 'site-a', 'Dept A', 'fixed', 1, 'A private note', 0), "
                    "('dept-b', 'site-b', 'Dept B', 'fixed', 2, 'B private note', 0), "
                    "('dept-c', 'site-c', 'Dept C', 'fixed', 3, 'C private note', 0)"
                )
            )
            user = User(
                tenant_id=tenant_a.id,
                username="admin-a",
                email="admin-a@example.test",
                password_hash="synthetic",
                role="admin",
                auth_version=1,
                is_active=True,
            )
            db.add(user)
            db.flush()
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                    "VALUES (:uid, :tid, 'site-a')"
                ),
                {"uid": user.id, "tid": tenant_a.id},
            )
            db.commit()
            app.config["F01A_USER_ID"] = user.id
            app.config["F01A_TENANT_ID"] = tenant_a.id
        finally:
            db.close()
    _enable_admin(app)
    try:
        yield app
    finally:
        from core import db as db_module

        if db_module._SessionFactory is not None:
            db_module._SessionFactory.remove()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._SessionFactory = None
        db_module._engine = None


def _authenticated_client(app):
    client = app.test_client()
    with client.session_transaction() as current:
        current.update(
            {
                "user_id": app.config["F01A_USER_ID"],
                "role": "admin",
                "tenant_id": app.config["F01A_TENANT_ID"],
                "auth_version": 1,
                "site_id": "site-a",
            }
        )
    return client


def test_admin_scope_allows_site_a_and_denies_other_sites_and_tenants(f01a_app):
    app = f01a_app
    client = _authenticated_client(app)

    sites = client.get("/admin/sites")
    assert sites.status_code == 200
    assert [item["id"] for item in sites.get_json()["items"]] == ["site-a"]

    own_departments = client.get("/admin/departments?site=site-a")
    assert own_departments.status_code == 200
    assert own_departments.get_json()["items"][0]["id"] == "dept-a"

    for site_id in ("site-b", "site-c"):
        response = client.get(f"/admin/departments?site={site_id}")
        assert response.status_code == 403

    own_notes = client.get("/admin/notes?scope=department&department_id=dept-a")
    assert own_notes.status_code == 200
    assert own_notes.get_json()["notes"] == "A private note"

    for department_id in ("dept-b", "dept-c"):
        notes = client.get(f"/admin/notes?scope=department&department_id={department_id}")
        diet = client.get(f"/admin/diet-defaults?department={department_id}")
        assert notes.status_code == 403
        assert diet.status_code == 403


def test_admin_scope_blocks_cross_site_writes_without_mutation(f01a_app):
    app = f01a_app
    client = _authenticated_client(app)

    before = get_session()
    try:
        snapshot = before.execute(
            text("SELECT notes, version FROM departments WHERE id='dept-b'")
        ).one()
    finally:
        before.close()

    for path, payload in (
        ("/admin/departments/dept-b", {"name": "Changed"}),
        ("/admin/departments/dept-b/notes", {"notes": "Changed"}),
        ("/admin/departments/dept-b/diet-defaults", {"items": []}),
    ):
        response = client.put(
            path,
            headers={"If-Match": 'W/"admin:dept:dept-b:v0"'},
            json=payload,
        )
        assert response.status_code == 403

    alt2 = client.put(
        "/admin/alt2",
        headers={"If-Match": 'W/"admin:alt2:week:1:v0"'},
        json={"week": 1, "items": [{"department_id": "dept-b", "weekday": 1, "enabled": True}]},
    )
    assert alt2.status_code == 403

    denied_create = client.post(
        "/admin/departments",
        json={"site_id": "site-b", "name": "Unauthorized", "resident_count_mode": "fixed"},
    )
    assert denied_create.status_code == 403

    after = get_session()
    try:
        assert after.execute(
            text("SELECT notes, version FROM departments WHERE id='dept-b'")
        ).one() == snapshot
        assert after.execute(
            text("SELECT COUNT(*) FROM departments WHERE name='Unauthorized'")
        ).scalar_one() == 0
    finally:
        after.close()


def test_admin_scope_revoked_site_binding_is_denied(f01a_app):
    app = f01a_app
    client = _authenticated_client(app)
    db = get_session()
    try:
        db.execute(text("DELETE FROM kitchen_user_sites WHERE site_id='site-a'"))
        db.commit()
    finally:
        db.close()

    response = client.get("/admin/departments?site=site-a")
    assert response.status_code == 401
