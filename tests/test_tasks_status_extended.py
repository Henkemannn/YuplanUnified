import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, User

ALLOWED = ["blocked", "cancelled", "doing", "done", "todo"]  # alphabetical


@pytest.fixture()
def app():
    return create_app({"TESTING": True, "SECRET_KEY": "test"})


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def seeded_admin():
    db = get_session()
    try:
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="T1")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        admin = db.query(User).filter_by(email="admin_status_ext@example.com").first()
        if not admin:
            admin = User(
                tenant_id=tenant.id,
                email="admin_status_ext@example.com",
                password_hash=generate_password_hash("pw"),
                role="admin",
                unit_id=None,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return {"tenant": tenant, "admin": admin}
    finally:
        db.close()


def login(client, email, password="pw"):
    # Bind session to a test site to satisfy strict site isolation
    with client.session_transaction() as sess:
        sess["site_id"] = "test-site"
    return client.post("/auth/login", json={"email": email, "password": password})


def test_post_201_and_location(client, seeded_admin):
    rv = login(client, "admin_status_ext@example.com")
    assert rv.status_code == 200
    rv = client.post("/tasks/", json={"title": "A new task"})
    assert rv.status_code == 201
    loc = rv.headers.get("Location")
    assert loc and loc.startswith("/tasks/")
    body = rv.get_json()
    assert body["task"]["status"] == "todo"


def test_patch_accepts_all_statuses(client, seeded_admin):
    rv = login(client, "admin_status_ext@example.com")
    assert rv.status_code == 200
    # create base
    rv = client.post("/tasks/", json={"title": "Base"})
    task_id = rv.get_json()["task"]["id"]
    for status in ALLOWED:
        rv2 = client.put(f"/tasks/{task_id}", json={"status": status})
        assert rv2.status_code == 200
        assert rv2.get_json()["task"]["status"] == status


def test_invalid_status_lists_allowed(client, seeded_admin):
    rv = login(client, "admin_status_ext@example.com")
    assert rv.status_code == 200
    rv = client.post("/tasks/", json={"title": "Base2"})
    task_id = rv.get_json()["task"]["id"]
    rv = client.put(f"/tasks/{task_id}", json={"status": "inprogress"})
    assert rv.status_code in (400, 422)
    data = rv.get_json()
    # detail should mention allowed list words
    txt = (data.get("detail") or "").lower()
    assert ("allowed" in txt) or ("validation" in data.get("type", ""))


def test_legacy_done_mapping(client, seeded_admin):
    rv = login(client, "admin_status_ext@example.com")
    assert rv.status_code == 200
    rv = client.post("/tasks/", json={"title": "Legacy1", "done": True})
    assert rv.status_code == 201
    data = rv.get_json()["task"]
    assert data["done"] is True and data["status"] == "done"
    task_id = data["id"]
    # Switch back via status
    rv2 = client.put(f"/tasks/{task_id}", json={"status": "todo"})
    assert rv2.status_code == 200
    d2 = rv2.get_json()["task"]
    assert d2["status"] == "todo" and d2["done"] is False
