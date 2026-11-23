import json

from flask import Flask

from core.app_factory import create_app


def _app():
    return create_app({"TESTING": True})


def _login(client):
    from core.db import get_session
    from core.models import User
    from core.admin_repo import SitesRepo
    from core.admin_user_repo import _set_user_site_binding

    db = get_session()
    try:
        site, _ = SitesRepo().create_site("Legacy Alias Site", tenant_id=1)
        site_id = str(site["id"])
        user = db.query(User).filter(User.id == 1).first()
        if user is None:
            user = User(id=1, tenant_id=1, username="legacy-admin", email="legacy-admin@example.test", password_hash="!", role="admin", is_active=True, auth_version=1)
            db.add(user)
        else:
            user.tenant_id = 1
            user.role = "admin"
            user.is_active = True
            user.auth_version = 1
        db.flush()
        _set_user_site_binding(db, user_id=int(user.id), tenant_id=1, site_id=site_id)
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 1
        sess["auth_version"] = 1
        sess["role"] = "admin"
        sess["site_id"] = site_id


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


def test_tasks_alias_is_quarantined():
    app: Flask = _app()
    with app.test_client() as client:
        _login(client)
        post_response = client.post("/tasks/", json={"title": "X"})
        assert post_response.status_code == 404
        assert post_response.get_json()["detail"] == "not_found"

        get_response = client.get("/tasks/")
        assert get_response.status_code == 404
        assert get_response.get_json()["detail"] == "not_found"
