import json
from typing import Any

from flask import Flask

from core.app_factory import create_app


def _client_app():
    app: Flask = create_app({"TESTING": True, "FEATURE_FLAGS": {"openapi_ui": True}})
    return app, app.test_client()


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
            note = Note(tenant_id=1, user_id=1, content=f"Note {i}")
            db.add(note)
        db.commit()
    finally:
        db.close()


def _login(client):
    # Minimal auth session seeding (simulate logged-in admin/tenant 1)
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 1
        sess["role"] = "admin"


def test_tasks_pagination_defaults():
    app, client = _client_app()
    _seed_tasks(app, 35)
    _login(client)
    resp = client.get("/tasks/")
    assert resp.status_code == 200
    data: dict[str, Any] = json.loads(resp.data)
    assert data["ok"] is True
    assert "items" in data and "meta" in data
    meta = data["meta"]
    assert meta["page"] == 1
    assert meta["size"] == 20
    assert meta["pages"] >= 2
    assert len(data["items"]) <= 20


def test_notes_pagination_custom():
    app, client = _client_app()
    _seed_notes(app, 30)
    _login(client)
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
    _seed_tasks(app, 5)
    _login(client)
    resp = client.get("/tasks/?size=0")
    assert resp.status_code == 400
    data: dict[str, Any] = json.loads(resp.data)
    assert data.get("ok") is False
    assert data.get("error") == "invalid"
