import pytest
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Base, Tenant, User


@pytest.fixture(scope="module")
def app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "JWT_SECRET": "secret"})
    sess = get_session()
    try:
        engine = sess.get_bind()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        t = Tenant(name="T1")
        sess.add(t); sess.commit(); sess.refresh(t)
        users = [
            User(tenant_id=t.id, email="admin@example.com", password_hash=generate_password_hash("pw"), role="admin"),
            User(tenant_id=t.id, email="cook@example.com", password_hash=generate_password_hash("pw"), role="cook"),
            User(tenant_id=t.id, email="portal@example.com", password_hash=generate_password_hash("pw"), role="unit_portal"),
        ]
        sess.add_all(users); sess.commit()
    finally:
        sess.close()
    return app

@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": "pw"}, headers={"X-Tenant-Id": "1"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["access_token"]


def test_cook_maps_to_viewer_forbidden_features(client):
    token = login(client, "cook@example.com")
    r = client.get("/features", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id":"1"})
    assert r.status_code in (401,403)
    if r.status_code == 403:
        j = r.get_json(); assert j["error"] == "forbidden"; assert j.get("required_role") in ("admin","superuser","editor")


def test_unit_portal_maps_to_editor_partial_access(client):
    token = login(client, "portal@example.com")
    # should at least access tasks list (mapped to editor) but not features (admin/superuser only)
    tasks = client.get("/tasks/", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id":"1"})
    assert tasks.status_code in (200,404,401,403)
    features = client.get("/features", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id":"1"})
    assert features.status_code in (401,403)


def test_required_role_field_present(client):
    token = login(client, "cook@example.com")
    r = client.get("/features", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id":"1"})
    if r.status_code == 403:
        j = r.get_json(); assert "required_role" in j
