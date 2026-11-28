from __future__ import annotations

import uuid

from werkzeug.security import generate_password_hash

from core.admin_user_repo import _set_user_site_binding
from core.db import get_session
from core.models import User


def seed_bound_user(
    client,
    *,
    site_id: str,
    role: str = "admin",
    department_id: str | None = None,
    email: str | None = None,
    password: str = "TestPassw0rd!2026",
) -> tuple[int, str]:
    email = email or f"health08f-{role}-{uuid.uuid4().hex}@example.test"
    app = client.application
    with app.app_context():
        db = get_session()
        try:
            user = User(
                tenant_id=1,
                email=email,
                username=email,
                password_hash=generate_password_hash(password),
                role=role,
                department_id=department_id,
                is_active=True,
                auth_version=1,
            )
            db.add(user)
            db.flush()
            _set_user_site_binding(
                db,
                user_id=int(user.id),
                tenant_id=1,
                site_id=str(site_id),
            )
            db.commit()
            user_id = int(user.id)
        finally:
            db.close()

    return user_id, email


def bind_user_to_site(client, *, user_id: int, site_id: str) -> None:
    with client.application.app_context():
        db = get_session()
        try:
            _set_user_site_binding(
                db,
                user_id=int(user_id),
                tenant_id=1,
                site_id=str(site_id),
            )
            db.commit()
        finally:
            db.close()


def login_bound_user(
    client,
    *,
    site_id: str,
    role: str = "admin",
    department_id: str | None = None,
    email: str | None = None,
    password: str = "TestPassw0rd!2026",
) -> int:
    user_id, email = seed_bound_user(
        client,
        site_id=site_id,
        role=role,
        department_id=department_id,
        email=email,
        password=password,
    )
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"X-Tenant-Id": "1"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    with client.session_transaction() as session:
        assert session.get("user_id") == user_id
        assert session.get("tenant_id") == 1
        assert session.get("role") == role
        if role == "superuser":
            assert session.get("site_id") in (None, str(site_id))
        else:
            assert session.get("site_id") == str(site_id)
            assert session.get("site_lock") is True
    return user_id


def login_existing_user(
    client,
    *,
    user_id: int,
    email: str,
    password: str,
    role: str,
    site_id: str | None,
) -> None:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"X-Tenant-Id": "1"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    with client.session_transaction() as session:
        assert session.get("user_id") == user_id
        assert session.get("tenant_id") == 1
        assert session.get("role") == role
        if role == "superuser":
            assert session.get("site_id") in (None, site_id)
        else:
            assert session.get("site_id") == site_id
            assert session.get("site_lock") is True
