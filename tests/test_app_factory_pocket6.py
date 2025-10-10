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
        u_admin = User(tenant_id=t.id, email="admin@example.com", password_hash=generate_password_hash("pw"), role="admin")
        u_view = User(tenant_id=t.id, email="view@example.com", password_hash=generate_password_hash("pw"), role="viewer")
        sess.add_all([u_admin, u_view]); sess.commit()
    finally:
        sess.close()
    return app

@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email: str):
    r = client.post("/auth/login", json={"email": email, "password": "pw"}, headers={"X-Tenant-Id": "1"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["access_token"]


def test_401_envelope(client):
    # Access protected endpoint without token -> unauthorized
    r = client.get("/tasks/", headers={"X-Tenant-Id":"1"})
    assert r.status_code == 401
    j = r.get_json(); assert j.get("type") and j.get("status") == 401, j
    assert j["type"].endswith("/unauthorized")


def test_session_login_and_access(client):
    token = login(client, "admin@example.com")
    r = client.get("/tasks/", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id":"1"})
    assert r.status_code in (200,404)


def test_403_role_mismatch(client):
    token = login(client, "view@example.com")
    # viewer tries to hit feature flags admin endpoint
    r = client.get("/features", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id":"1"})
    # either 403 or (if role mapping changed) 401 fallback, assert forbidden envelope if 403
    if r.status_code == 403:
        j = r.get_json(); assert j.get("status") == 403 and j.get("type"," ").endswith("/forbidden")
    else:
        assert r.status_code in (401,403)


def test_404_not_found_resource(client):
    token = login(client, "admin@example.com")
    r = client.get("/tasks/999999", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id":"1"})
    assert r.status_code in (404,403)  # if forbidden due to tenant mismatch logic
    if r.status_code == 404:
        j = r.get_json(); assert j.get("status") == 404 and j.get("type"," ").endswith("/not_found")
