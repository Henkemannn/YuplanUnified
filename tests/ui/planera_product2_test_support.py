from __future__ import annotations

import uuid

from sqlalchemy import text

from core.db import get_session
from core.models import User


def authenticate_product2_client(
    client,
    *,
    tenant_id: int,
    site_id: str,
    role: str,
) -> None:
    """Create the explicitly requested test identity and bind its session."""
    db = get_session()
    try:
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                "UNIQUE(user_id, tenant_id, site_id))"
            )
        )
        user = User(
            tenant_id=tenant_id,
            username=f"product2-test-{role}-{uuid.uuid4().hex}",
            email=f"product2-test-{role}-{uuid.uuid4().hex}@example.test",
            password_hash="fixture-only",
            role=role,
            auth_version=1,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, :tenant_id, :site_id)"
            ),
            {"user_id": user.id, "tenant_id": tenant_id, "site_id": site_id},
        )
        db.commit()
        with client.session_transaction() as session:
            session.update(
                {
                    "user_id": user.id,
                    "role": role,
                    "tenant_id": tenant_id,
                    "site_id": site_id,
                    "auth_version": 1,
                }
            )
    finally:
        db.close()
