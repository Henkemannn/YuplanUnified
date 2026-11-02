import json

from flask import Flask

from core.app_factory import create_app


def _app():
    return create_app({"TESTING": True})


def _login(client):
    from core.db import get_session
    from core.models import User

    db = get_session()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if user is None:
            user = User(id=1, tenant_id=1, username="legacy-admin", email="legacy-admin@example.test", password_hash="!", role="admin", is_active=True, auth_version=1)
            db.add(user)
        else:
            user.tenant_id = 1
            user.role = "admin"
            user.is_active = True
            user.auth_version = 1
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 1
        sess["auth_version"] = 1
        sess["role"] = "admin"


def test_notes_alias_has_deprecation_headers():
    app: Flask = _app()
    with app.test_client() as client:
        _login(client)
        # create one note
        client.post("/notes/", json={"content": "Hello"})
        resp = client.get("/notes/")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "notes" in data and "items" in data
        assert resp.headers.get("Deprecation") == "true"
        assert "Sunset" in resp.headers
        link = resp.headers.get("Link")
        assert link and 'rel="deprecation"' in link


def test_tasks_alias_has_deprecation_headers():
    app: Flask = _app()
    with app.test_client() as client:
        _login(client)
        # create one task
        client.post("/tasks/", json={"title": "X"})
        resp = client.get("/tasks/")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "tasks" in data and "items" in data
        assert resp.headers.get("Deprecation") == "true"
        assert "Sunset" in resp.headers
        link = resp.headers.get("Link")
        assert link and 'rel="deprecation"' in link
