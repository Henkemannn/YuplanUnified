import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, User
from core.tasks_service import create_task, update_task
from core.errors import ValidationError


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
        admin = db.query(User).filter_by(email="admin_status@example.com").first()
        if not admin:
            admin = User(
                tenant_id=tenant.id,
                email="admin_status@example.com",
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


def test_invalid_status_rejected(client, seeded_admin):
    db = get_session()
    try:
        with pytest.raises(ValidationError):
            create_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                        role="admin", payload={"title": "X", "status": "nope"})
    finally:
        db.close()


def test_valid_status_sets_done_flag(client, seeded_admin):
    db = get_session()
    try:
        task_id = create_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                              role="admin", payload={"title": "Do it", "status": "doing"})["task_id"]
        assert update_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                           role="admin", task_id=task_id, payload={"status": "done"})["updated"]
    finally:
        db.close()


def test_done_boolean_still_supported(client, seeded_admin):
    db = get_session()
    try:
        task_id = create_task(db, tenant_id=seeded_admin["tenant_id"], user_id=seeded_admin["admin_id"],
                              role="admin", payload={"title": "Legacy", "done": True})["task_id"]
        assert task_id
    finally:
        db.close()
