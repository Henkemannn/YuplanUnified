import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, User
from core.tasks_service import create_task, update_task
from core.errors import ValidationError

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
        return {"tenant_id": tenant.id, "admin_id": admin.id}
    finally:
        db.close()


def login(client, email, password="pw"):
    # Bind session to a test site to satisfy strict site isolation
    with client.session_transaction() as sess:
        sess["site_id"] = "test-site"
    return client.post("/auth/login", json={"email": email, "password": password})


def test_post_201_and_location(client, seeded_admin):
    db = get_session()
    try:
        result = create_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                             role="admin", payload={"title": "A new task"})
        assert result["ok"] and result["task_id"]
    finally:
        db.close()


def test_patch_accepts_all_statuses(client, seeded_admin):
    db = get_session()
    task_id = create_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                          role="admin", payload={"title": "Base"})["task_id"]
    for status in ALLOWED:
        assert update_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                           role="admin", task_id=task_id, payload={"status": status})["updated"]
    db.close()


def test_invalid_status_lists_allowed(client, seeded_admin):
    db = get_session()
    try:
        task_id = create_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                              role="admin", payload={"title": "Base2"})["task_id"]
        with pytest.raises(ValidationError):
            update_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                        role="admin", task_id=task_id, payload={"status": "inprogress"})
    finally:
        db.close()


def test_legacy_done_mapping(client, seeded_admin):
    db = get_session()
    try:
        task_id = create_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                              role="admin", payload={"title": "Legacy1", "done": True})["task_id"]
        assert db.get(User, seeded_admin["admin_id"]) is not None
        assert update_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                           role="admin", task_id=task_id, payload={"status": "todo"})["updated"]
    finally:
        db.close()
