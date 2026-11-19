import re
import uuid

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.db import get_session
from core.models import User


def _seed_activation_fixture(app_session):
    site_id = f"activation-site-{uuid.uuid4().hex}"
    admin_email = f"activation-admin-{uuid.uuid4().hex[:8]}@example.com"
    target_email = f"activation-target-{uuid.uuid4().hex[:8]}@example.com"
    foreign_email = f"activation-foreign-{uuid.uuid4().hex[:8]}@example.com"
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
                    "VALUES (:sid, 'Activation Site', 1, 0)"
                ),
                {"sid": site_id},
            )
            db.execute(
                text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES (2, 'Foreign Tenant', 1)")
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
                    "VALUES (:sid, 'Foreign Site', 2, 0)"
                ),
                {"sid": f"{site_id}-foreign"},
            )
            admin = User(
                tenant_id=1,
                email=admin_email,
                username=admin_email,
                password_hash=generate_password_hash("ActivationPassw0rd!"),
                role="admin",
                is_active=True,
            )
            target = User(
                tenant_id=1,
                email=target_email,
                username=target_email,
                password_hash="hash",
                role="staff",
                is_active=False,
            )
            foreign = User(
                tenant_id=2,
                email=foreign_email,
                username=foreign_email,
                password_hash="hash",
                role="staff",
                is_active=False,
            )
            db.add_all([admin, target, foreign])
            db.flush()
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:uid, 1, :sid)"
                ),
                {"uid": admin.id, "sid": site_id},
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:uid, 1, :sid)"
                ),
                {"uid": target.id, "sid": site_id},
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:uid, 2, :sid)"
                ),
                {"uid": foreign.id, "sid": f"{site_id}-foreign"},
            )
            db.commit()
            return admin_email, target.id, foreign.id
        finally:
            db.close()


def _csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_real_admin_can_activate_site_bound_user(app_session):
    admin_email, target_id, _foreign_id = _seed_activation_fixture(app_session)
    client = app_session.test_client()

    login = client.post(
        "/auth/login",
        json={"email": admin_email, "password": "ActivationPassw0rd!"},
        headers={"Accept": "application/json"},
    )
    assert login.status_code == 200

    listing = client.get("/ui/admin/users", headers={"Accept": "text/html"})
    assert listing.status_code == 200
    activate = client.post(
        f"/ui/admin/users/{target_id}/activate",
        data={"csrf_token": _csrf_token(listing.data.decode("utf-8"))},
        follow_redirects=True,
    )
    assert activate.status_code == 200

    with app_session.app_context():
        db = get_session()
        try:
            assert db.execute(
                text("SELECT is_active FROM users WHERE id=:uid"),
                {"uid": target_id},
            ).scalar_one() == 1
        finally:
            db.close()


def test_real_admin_cannot_activate_foreign_user(app_session):
    admin_email, _target_id, foreign_id = _seed_activation_fixture(app_session)
    client = app_session.test_client()
    login = client.post(
        "/auth/login",
        json={"email": admin_email, "password": "ActivationPassw0rd!"},
        headers={"Accept": "application/json"},
    )
    assert login.status_code == 200
    listing = client.get("/ui/admin/users")
    response = client.post(
        f"/ui/admin/users/{foreign_id}/activate",
        data={"csrf_token": _csrf_token(listing.data.decode("utf-8"))},
    )
    assert response.status_code == 404


def test_activation_rejects_deleted_user(app_session):
    admin_email, target_id, _foreign_id = _seed_activation_fixture(app_session)
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text("UPDATE users SET deleted_at=CURRENT_TIMESTAMP WHERE id=:uid"),
                {"uid": target_id},
            )
            db.commit()
        finally:
            db.close()

    client = app_session.test_client()
    login = client.post(
        "/auth/login",
        json={"email": admin_email, "password": "ActivationPassw0rd!"},
        headers={"Accept": "application/json"},
    )
    assert login.status_code == 200
    listing = client.get("/ui/admin/users")
    response = client.post(
        f"/ui/admin/users/{target_id}/activate",
        data={"csrf_token": _csrf_token(listing.data.decode("utf-8"))},
    )
    assert response.status_code == 404
