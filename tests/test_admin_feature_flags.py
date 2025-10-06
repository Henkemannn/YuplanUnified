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
def tenants_and_users():
    db = get_session()
    try:
        tenants = db.query(Tenant).all()
        if len(tenants) < 2:
            while len(tenants) < 2:
                t = Tenant(name=f"T{len(tenants)+1}")
                db.add(t); db.commit(); db.refresh(t)
                tenants.append(t)
        t1, t2 = tenants[:2]
        # Users ensure
        def ensure(email, role, tenant_id):
            u = db.query(User).filter_by(email=email).first()
            if not u:
                u = User(tenant_id=tenant_id, email=email, password_hash=generate_password_hash("pw"), role=role, unit_id=None)
                db.add(u); db.commit(); db.refresh(u)
            return u
        su = ensure("root@example.com","superuser", t1.id)
        admin1 = ensure("admin_t1@example.com","admin", t1.id)
        admin2 = ensure("admin_t2@example.com","admin", t2.id)
        # Return only ids to avoid detached instances
        return {
            "t1": type("TObj",(object,),{"id": t1.id})(),
            "t2": type("TObj",(object,),{"id": t2.id})(),
            "su": su,
            "admin1": admin1,
            "admin2": admin2
        }
    finally:
        db.close()


def login(client, email, password="pw"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_superuser_toggle_any_tenant(client, tenants_and_users):
    login(client, "root@example.com")
    # toggle inline_ui on tenant2
    rv = client.post("/admin/feature_flags", json={"name":"inline_ui","enabled": True, "tenant_id": tenants_and_users["t2"].id})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["tenant_id"] == tenants_and_users["t2"].id
    assert "inline_ui" in data["features"]


def test_admin_cannot_target_other_tenant(client, tenants_and_users):
    login(client, "admin_t1@example.com")
    # tries to pass tenant_id = t2 (should be ignored and only act on own tenant t1)
    rv = client.post("/admin/feature_flags", json={"name":"inline_ui","enabled": True, "tenant_id": tenants_and_users["t2"].id})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["tenant_id"] == tenants_and_users["t1"].id


def test_missing_fields_validation_error(client, tenants_and_users):
    login(client, "admin_t1@example.com")
    rv = client.post("/admin/feature_flags", json={"name":"", "enabled": True})
    assert rv.status_code == 400
    data = rv.get_json()
    assert data["error"] in ("validation_error","bad_request")


def test_disable_feature(client, tenants_and_users):
    login(client, "root@example.com")
    # enable then disable
    client.post("/admin/feature_flags", json={"name":"inline_ui","enabled": True, "tenant_id": tenants_and_users["t1"].id})
    rv = client.post("/admin/feature_flags", json={"name":"inline_ui","enabled": False, "tenant_id": tenants_and_users["t1"].id})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["enabled"] is False
    assert "inline_ui" not in data["features"]
