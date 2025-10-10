import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, User


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
            db.add(tenant); db.commit(); db.refresh(tenant)
        admin = db.query(User).filter_by(email="admin_status@example.com").first()
        if not admin:
            admin = User(tenant_id=tenant.id, email="admin_status@example.com", password_hash=generate_password_hash("pw"), role="admin", unit_id=None)
            db.add(admin); db.commit(); db.refresh(admin)
        return {"tenant": tenant, "admin": admin}
    finally:
        db.close()

def login(client, email, password="pw"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_invalid_status_rejected(client, seeded_admin):
    rv = login(client, "admin_status@example.com")
    assert rv.status_code == 200
    rv = client.post("/tasks/", json={"title": "X", "status": "nope"})
    assert rv.status_code in (400, 422)
    data = rv.get_json()
    # RFC7807 ProblemDetails
    assert data.get("status") in (400,422)
    assert any(s in data.get("type"," ") for s in ["/validation_error","/bad_request"])


def test_valid_status_sets_done_flag(client, seeded_admin):
    rv = login(client, "admin_status@example.com")
    assert rv.status_code == 200
    rv = client.post("/tasks/", json={"title": "Do it", "status": "doing"})
    assert rv.status_code == 201
    assert rv.get_json()["task"]["done"] is False
    # update to done via status
    task_id = rv.get_json()["task"]["id"]
    rv = client.put(f"/tasks/{task_id}", json={"status": "done"})
    assert rv.status_code == 200
    assert rv.get_json()["task"]["done"] is True


def test_done_boolean_still_supported(client, seeded_admin):
    rv = login(client, "admin_status@example.com")
    assert rv.status_code == 200
    rv = client.post("/tasks/", json={"title": "Legacy", "done": True})
    assert rv.status_code == 201
    assert rv.get_json()["task"]["done"] is True
