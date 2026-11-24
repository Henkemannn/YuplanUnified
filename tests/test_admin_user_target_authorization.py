from __future__ import annotations

import uuid

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.db import get_session
from core.models import Tenant, User


def _seed_scope(app_session):
    suffix = uuid.uuid4().hex[:8]
    with app_session.app_context():
        db = get_session()
        try:
            tenant_a = Tenant(name=f"08B Tenant A {suffix}")
            tenant_b = Tenant(name=f"08B Tenant B {suffix}")
            db.add_all([tenant_a, tenant_b])
            db.flush()
            sites = {}
            for tenant_id, label in (
                (tenant_a.id, "A"),
                (tenant_a.id, "A2"),
                (tenant_b.id, "B"),
            ):
                site_id = f"08b-{suffix}-{label.lower()}"
                db.execute(
                    text("INSERT INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, :tid, 0)"),
                    {"sid": site_id, "name": f"08B Site {label}", "tid": int(tenant_id)},
                )
                sites[label] = site_id

            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            admin_a = User(
                tenant_id=tenant_a.id,
                email=f"08b-admin-a-{suffix}@example.com",
                username=f"08b-admin-a-{suffix}",
                password_hash=generate_password_hash("AdminPassw0rd!2026"),
                role="admin",
                is_active=True,
                auth_version=1,
            )
            admin_a2 = User(
                tenant_id=tenant_a.id,
                email=f"08b-admin-a2-{suffix}@example.com",
                username=f"08b-admin-a2-{suffix}",
                password_hash=generate_password_hash("AdminPassw0rd!2026"),
                role="admin",
                is_active=True,
                auth_version=1,
            )
            admin_same = User(
                tenant_id=tenant_a.id,
                email=f"08b-admin-same-{suffix}@example.com",
                username=f"08b-admin-same-{suffix}",
                password_hash=generate_password_hash("AdminPassw0rd!2026"),
                role="admin",
                is_active=True,
                auth_version=1,
            )
            admin_b = User(
                tenant_id=tenant_b.id,
                email=f"08b-admin-b-{suffix}@example.com",
                username=f"08b-admin-b-{suffix}",
                password_hash=generate_password_hash("AdminPassw0rd!2026"),
                role="admin",
                is_active=True,
                auth_version=1,
            )
            superuser = User(
                tenant_id=tenant_a.id,
                email=f"08b-superuser-{suffix}@example.com",
                username=f"08b-superuser-{suffix}",
                password_hash=generate_password_hash("SuperPassw0rd!2026"),
                role="superuser",
                is_active=True,
                auth_version=1,
            )
            db.add_all([admin_a, admin_a2, admin_same, admin_b, superuser])
            db.flush()
            bindings = (
                (admin_a.id, tenant_a.id, sites["A"]),
                (admin_a2.id, tenant_a.id, sites["A2"]),
                (admin_same.id, tenant_a.id, sites["A"]),
                (admin_b.id, tenant_b.id, sites["B"]),
                (superuser.id, tenant_a.id, sites["A"]),
            )
            for user_id, tenant_id, site_id in bindings:
                db.execute(
                    text(
                        "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                        "VALUES(:uid, :tid, :sid)"
                    ),
                    {"uid": int(user_id), "tid": int(tenant_id), "sid": site_id},
                )
            db.commit()
            return {
                "tenant_a": int(tenant_a.id),
                "tenant_b": int(tenant_b.id),
                "site_a": sites["A"],
                "site_a2": sites["A2"],
                "site_b": sites["B"],
                "admin_a": admin_a.email,
                "admin_a2": admin_a2.email,
                "admin_same": admin_same.email,
                "admin_b": admin_b.email,
                "superuser": superuser.email,
            }
        finally:
            db.close()


def _create_user(app_session, *, tenant_id, email, role, site_id=None, department_id=None):
    with app_session.app_context():
        db = get_session()
        try:
            user = User(
                tenant_id=tenant_id,
                email=email,
                username=email.split("@", 1)[0],
                password_hash=generate_password_hash("TargetPassw0rd!2026"),
                role=role,
                is_active=True,
                auth_version=1,
                department_id=department_id,
            )
            db.add(user)
            db.flush()
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            if site_id:
                db.execute(
                    text(
                        "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                        "VALUES(:uid, :tid, :sid)"
                    ),
                    {"uid": int(user.id), "tid": int(tenant_id), "sid": site_id},
                )
            db.commit()
            return int(user.id)
        finally:
            db.close()


def _login(client, email, password="AdminPassw0rd!2026"):
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, response.get_json()


def _snapshot(app_session, user_id):
    with app_session.app_context():
        db = get_session()
        try:
            user = db.execute(
                text("SELECT password_hash, auth_version, role, is_active, tenant_id FROM users WHERE id=:uid"),
                {"uid": int(user_id)},
            ).fetchone()
            binding = db.execute(
                text("SELECT tenant_id, site_id FROM kitchen_user_sites WHERE user_id=:uid"),
                {"uid": int(user_id)},
            ).fetchone()
            return tuple(user) if user else None, tuple(binding) if binding else None
        finally:
            db.close()


def test_real_admin_can_create_and_manage_site_bound_staff(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["admin_a"])
    staff_suffix = uuid.uuid4().hex[:8]
    staff_email = f"08b-created-staff-{staff_suffix}@example.com"
    staff_username = f"08b-created-staff-{staff_suffix}"

    created = client.post(
        "/ui/admin/users/new",
        data={
            "email": staff_email,
            "username": staff_username,
            "full_name": "Created Staff",
            "password": "StaffPassw0rd!2026",
            "role": "staff",
        },
        follow_redirects=False,
    )
    assert created.status_code == 302

    with app_session.app_context():
        db = get_session()
        try:
            staff_id = db.execute(
                text("SELECT id FROM users WHERE email=:email"),
                {"email": staff_email},
            ).scalar_one()
            binding = db.execute(
                text("SELECT tenant_id, site_id FROM kitchen_user_sites WHERE user_id=:uid"),
                {"uid": int(staff_id)},
            ).fetchone()
        finally:
            db.close()
    assert tuple(binding) == (data["tenant_a"], data["site_a"])

    updated = client.post(
        f"/ui/admin/users/{staff_id}/edit",
        data={
            "email": staff_email,
            "username": staff_username,
            "full_name": "Updated Staff",
            "role": "staff",
        },
        follow_redirects=False,
    )
    assert updated.status_code == 302


def test_site_binding_failure_rolls_back_create_and_update(app_session, monkeypatch):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["admin_a"])

    def fail_binding(*args, **kwargs):
        raise RuntimeError("simulated site-binding failure")

    monkeypatch.setattr("core.admin_user_repo._set_user_site_binding", fail_binding)
    response = client.post(
        "/ui/admin/users/new",
        data={
            "email": "08b-atomic-create@example.com",
            "username": "08b-atomic-create",
            "full_name": "Atomic Create",
            "password": "StaffPassw0rd!2026",
            "role": "staff",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app_session.app_context():
        db = get_session()
        try:
            assert db.execute(
                text("SELECT 1 FROM users WHERE email='08b-atomic-create@example.com'")
            ).fetchone() is None
        finally:
            db.close()

    target_id = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b-atomic-update@example.com",
        role="staff",
        site_id=data["site_a"],
    )
    before = _snapshot(app_session, target_id)
    response = client.post(
        f"/ui/admin/users/{target_id}/edit",
        data={
            "email": "08b-atomic-update-changed@example.com",
            "username": "08b-atomic-update-changed",
            "full_name": "Should Roll Back",
            "role": "staff",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert _snapshot(app_session, target_id) == before


def test_create_site_binding_uses_users_site_id_when_available(app_session):
    data = _seed_scope(app_session)
    with app_session.app_context():
        db = get_session()
        try:
            columns = {
                str(row[1])
                for row in db.execute(text("PRAGMA table_info(users)")).fetchall()
            }
            if "site_id" not in columns:
                db.execute(text("ALTER TABLE users ADD COLUMN site_id TEXT"))
                db.commit()
        finally:
            db.close()

    client = app_session.test_client()
    _login(client, data["admin_a"])
    response = client.post(
        "/ui/admin/users/new",
        data={
            "email": "08b-site-column@example.com",
            "username": "08b-site-column",
            "full_name": "Site Column Staff",
            "password": "StaffPassw0rd!2026",
            "role": "staff",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT site_id FROM users WHERE email='08b-site-column@example.com'")
            ).fetchone()
        finally:
            db.close()
    assert row is not None
    assert row[0] == data["site_a"]


def test_other_site_and_cross_tenant_admins_cannot_mutate_target(app_session):
    data = _seed_scope(app_session)
    staff_a = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b-site-a-staff@example.com",
        role="staff",
        site_id=data["site_a"],
    )
    staff_b = _create_user(
        app_session,
        tenant_id=data["tenant_b"],
        email="08b-site-b-staff@example.com",
        role="staff",
        site_id=data["site_b"],
    )

    same_site_client = app_session.test_client()
    _login(same_site_client, data["admin_same"])
    assert same_site_client.get(f"/ui/admin/users/{staff_a}/edit").status_code == 200

    for email, target_id in ((data["admin_a2"], staff_a), (data["admin_a"], staff_b)):
        client = app_session.test_client()
        _login(client, email)
        before = _snapshot(app_session, target_id)
        assert client.get(f"/ui/admin/users/{target_id}/edit").status_code == 404
        for endpoint, form in (
            (f"/ui/admin/users/{target_id}/edit", {"email": "changed@example.com", "role": "staff"}),
            (f"/ui/admin/users/{target_id}/deactivate", {}),
            (f"/ui/admin/users/{target_id}/reset-password", {}),
        ):
            response = client.post(endpoint, data=form, follow_redirects=False)
            assert response.status_code == 404
        assert _snapshot(app_session, target_id) == before


def test_unbound_and_conflicting_bindings_are_denied(app_session):
    data = _seed_scope(app_session)
    unbound = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b-unbound@example.com",
        role="staff",
    )
    conflicting = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b-conflicting@example.com",
        role="staff",
        site_id=data["site_a"],
    )
    department_id = f"08b-conflict-dept-{uuid.uuid4().hex[:8]}"
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode) "
                    "VALUES(:did, :sid, 'Conflict department', 'manual')"
                ),
                {"did": department_id, "sid": data["site_a2"]},
            )
            db.execute(
                text(
                    "UPDATE users SET department_id=:did WHERE id=:uid"
                ),
                {"did": department_id, "uid": conflicting},
            )
            db.commit()
        finally:
            db.close()

    client = app_session.test_client()
    _login(client, data["admin_a"])
    for target_id in (unbound, conflicting):
        before = _snapshot(app_session, target_id)
        assert client.get(f"/ui/admin/users/{target_id}/edit").status_code == 404
        response = client.post(
            f"/ui/admin/users/{target_id}/reset-password",
            follow_redirects=False,
        )
        assert response.status_code == 404
        assert _snapshot(app_session, target_id) == before


def test_admin_cannot_manage_superuser_or_escalate_role(app_session):
    data = _seed_scope(app_session)
    staff_id = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b-escalation@example.com",
        role="staff",
        site_id=data["site_a"],
    )
    with app_session.app_context():
        db = get_session()
        try:
            superuser_id = db.execute(
                text("SELECT id FROM users WHERE email=:email"),
                {"email": data["superuser"]},
            ).scalar_one()
        finally:
            db.close()

    client = app_session.test_client()
    _login(client, data["admin_a"])
    before_superuser = _snapshot(app_session, superuser_id)
    for endpoint, form in (
        (f"/ui/admin/users/{superuser_id}/edit", {"email": "changed@example.com", "role": "admin"}),
        (f"/ui/admin/users/{superuser_id}/deactivate", {}),
        (f"/ui/admin/users/{superuser_id}/reset-password", {}),
    ):
        response = client.post(endpoint, data=form, follow_redirects=False)
        assert response.status_code == 404
    assert client.get(f"/ui/admin/users/{superuser_id}/edit").status_code == 404
    assert _snapshot(app_session, superuser_id) == before_superuser

    before_staff = _snapshot(app_session, staff_id)
    response = client.post(
        f"/ui/admin/users/{staff_id}/edit",
        data={"email": "08b-escalation@example.com", "username": "08b-escalation", "role": "superuser"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert _snapshot(app_session, staff_id) == before_staff


def test_kitchen_user_delete_is_site_bound(app_session):
    data = _seed_scope(app_session)
    kitchen_b = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b-kitchen-b@example.com",
        role="kitchen",
        site_id=data["site_a2"],
    )
    client = app_session.test_client()
    _login(client, data["admin_a"])
    before = _snapshot(app_session, kitchen_b)

    response = client.post(
        f"/ui/admin/kitchen-users/{kitchen_b}/delete",
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert _snapshot(app_session, kitchen_b) == before
