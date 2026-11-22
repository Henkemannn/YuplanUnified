import json
from typing import Any

from flask import Flask

from core.app_factory import create_app


def _client_app():
    app: Flask = create_app({"TESTING": True, "FEATURE_FLAGS": {"openapi_ui": True}})
    return app, app.test_client()


def _ensure_auth_user(app: Flask) -> tuple[int, int]:
    from core.db import get_session
    from core.models import Site, Tenant, User
    from sqlalchemy import text

    with app.app_context():
        db = get_session()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            if tenant is None:
                db.add(Tenant(id=1, name="Pagination Test Tenant"))
            user = db.query(User).filter(User.id == 1).first()
            if user is None:
                user = User(
                    id=1,
                    tenant_id=1,
                    username="pagination-admin",
                    email="pagination-admin@example.test",
                    password_hash="!",
                    role="admin",
                    is_active=True,
                    auth_version=1,
                )
                db.add(user)
            else:
                user.tenant_id = 1
                user.role = "admin"
                user.is_active = True
                user.auth_version = 1
            db.commit()
            if db.get(Site, "pagination-site") is None:
                db.add(Site(id="pagination-site", tenant_id=1, name="Pagination Site"))
                db.commit()
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites "
                    "(user_id INTEGER, tenant_id INTEGER, site_id TEXT)"
                )
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:uid, 1, 'pagination-site')"
                ),
                {"uid": user.id},
            )
            db.commit()
            return int(user.id), int(user.auth_version or 1)
        finally:
            db.close()


def _seed_tasks(app: Flask, n: int):
    # Direct DB seed (simplified) - using model import inline to avoid circular
    from core.db import get_session
    from core.models import Task

    db = get_session()
    try:
        for i in range(n):
            t = Task(title=f"T{i}", task_type="prep", tenant_id=1, creator_user_id=1)
            db.add(t)
        db.commit()
    finally:
        db.close()


def _seed_notes(app: Flask, n: int):
    from core.db import get_session
    from core.models import Note

    db = get_session()
    try:
        for i in range(n):
            note = Note(tenant_id=1, site_id="pagination-site", user_id=1, content=f"Note {i}")
            db.add(note)
        db.commit()
    finally:
        db.close()


def _login(client, user_id: int, auth_version: int):
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = user_id
        sess["role"] = "admin"
        sess["auth_version"] = auth_version
        sess["site_id"] = "pagination-site"


def test_tasks_pagination_defaults():
    app, client = _client_app()
    user_id, auth_version = _ensure_auth_user(app)
    _login(client, user_id, auth_version)
    resp = client.get("/tasks/")
    assert resp.status_code == 404
    assert "Task" not in resp.get_data(as_text=True)


def test_notes_pagination_custom():
    app, client = _client_app()
    user_id, auth_version = _ensure_auth_user(app)
    _seed_notes(app, 30)
    _login(client, user_id, auth_version)
    resp = client.get("/notes/?page=2&size=5")
    assert resp.status_code == 200
    data: dict[str, Any] = json.loads(resp.data)
    assert data["ok"] is True
    meta = data["meta"]
    assert meta["page"] == 2
    assert meta["size"] == 5
    assert len(data["items"]) == 5


def test_tasks_pagination_invalid_size():
    app, client = _client_app()
    user_id, auth_version = _ensure_auth_user(app)
    _login(client, user_id, auth_version)
    resp = client.get("/tasks/?size=0")
    assert resp.status_code == 404
    assert "Task" not in resp.get_data(as_text=True)
