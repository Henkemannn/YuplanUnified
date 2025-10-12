import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, TenantFeatureFlag, User


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
                t = Tenant(name=f"T{len(tenants) + 1}")
                db.add(t)
                db.commit()
                db.refresh(t)
                tenants.append(t)
        t1, t2 = tenants[:2]

        def ensure(email, role, tenant_id):
            u = db.query(User).filter_by(email=email).first()
            if not u:
                u = User(
                    tenant_id=tenant_id,
                    email=email,
                    password_hash=generate_password_hash("pw"),
                    role=role,
                    unit_id=None,
                )
                db.add(u)
                db.commit()
                db.refresh(u)
            return u

        su = ensure("root2@example.com", "superuser", t1.id)
        admin1 = ensure("admin_t1b@example.com", "admin", t1.id)
        admin2 = ensure("admin_t2b@example.com", "admin", t2.id)
        # Seed one flag for tenant2 directly
        flag = db.query(TenantFeatureFlag).filter_by(tenant_id=t2.id, name="inline_ui").first()
        if not flag:
            db.add(TenantFeatureFlag(tenant_id=t2.id, name="inline_ui", enabled=True))
            db.commit()
        return {"t1": t1.id, "t2": t2.id, "su": su, "admin1": admin1, "admin2": admin2}
    finally:
        db.close()


def login(client, email, password="pw"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_superuser_list_other_tenant_flags(client, tenants_and_users):
    login(client, "root2@example.com")
    rv = client.get(f"/admin/feature_flags?tenant_id={tenants_and_users['t2']}")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["tenant_id"] == tenants_and_users["t2"]
    assert "inline_ui" in data["features"]


def test_admin_cannot_override_tenant_id(client, tenants_and_users):
    login(client, "admin_t1b@example.com")
    # Pass explicit other tenant id, should ignore and still return own
    rv = client.get(f"/admin/feature_flags?tenant_id={tenants_and_users['t2']}")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["tenant_id"] == tenants_and_users["t1"]


def test_missing_context_returns_400(client):
    # Not logged in / no session tenant
    rv = client.get("/admin/feature_flags")
    assert rv.status_code == 401 or rv.status_code == 400  # depends if auth kicks in first
