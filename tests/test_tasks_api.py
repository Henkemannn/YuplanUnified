import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, User


@pytest.fixture()
def app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    return app

@pytest.fixture()
def client(app: Flask):
    return app.test_client()

@pytest.fixture()
def seeded_users():
    db = get_session()
    try:
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="T1")
            db.add(tenant); db.commit(); db.refresh(tenant)
        admin = User(tenant_id=tenant.id, email="admin2@example.com", password_hash=generate_password_hash("pw"), role="admin", unit_id=None)
        cook = User(tenant_id=tenant.id, email="cook2@example.com", password_hash=generate_password_hash("pw"), role="cook", unit_id=None)
        db.add_all([admin, cook]); db.commit(); db.refresh(admin); db.refresh(cook)
        return {"tenant": tenant, "admin": admin, "cook": cook}
    finally:
        db.close()

def login(client, email, password="pw"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_tasks_crud_and_private_permissions(client, seeded_users):
    # login as admin
    rv = login(client, "admin2@example.com")
    assert rv.status_code == 200
    # create public task
    rv = client.post("/tasks/", json={"title": "Chop onions", "task_type": "prep"})
    assert rv.status_code == 201
    public_task = rv.get_json()["task"]
    # create private task
    rv = client.post("/tasks/", json={"title": "Secret marinade", "private_flag": True})
    assert rv.status_code == 201
    private_task = rv.get_json()["task"]

    # list tasks as admin -> see both
    rv = client.get("/tasks/")
    data = rv.get_json()
    ids = {t["id"] for t in data["tasks"]}
    assert public_task["id"] in ids and private_task["id"] in ids

    # logout and login as cook
    client.post("/auth/logout")
    rv = login(client, "cook2@example.com")
    assert rv.status_code == 200

    # list tasks as non-owner cook (should not see private)
    rv = client.get("/tasks/")
    data = rv.get_json()
    ids = {t["id"] for t in data["tasks"]}
    assert public_task["id"] in ids
    assert private_task["id"] not in ids

    # attempt update private task (should fail)
    rv = client.put(f"/tasks/{private_task['id']}", json={"title": "Hack"})
    assert rv.status_code == 403

    # update public task (non-owner) -> now forbidden under ownership enforcement
    rv = client.put(f"/tasks/{public_task['id']}", json={"done": True})
    assert rv.status_code == 403

    # delete private task (should fail)
    rv = client.delete(f"/tasks/{private_task['id']}")
    assert rv.status_code == 403

    # login back as admin and delete
    client.post("/auth/logout")
    rv = login(client, "admin2@example.com")
    assert rv.status_code == 200
    rv = client.delete(f"/tasks/{public_task['id']}")
    assert rv.status_code == 200
    # ensure deletion
    rv = client.get("/tasks/")
    ids_after = {t["id"] for t in rv.get_json()["tasks"]}
    assert public_task["id"] not in ids_after

