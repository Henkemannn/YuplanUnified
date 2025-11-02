from __future__ import annotations

from core.db import get_session
from core.models import User


def _seed_two_users(tenant_id: int = 1):
    db = get_session()
    try:
        u1 = db.query(User).filter_by(tenant_id=tenant_id, email="a@ex").first()
        if not u1:
            u1 = User(tenant_id=tenant_id, email="a@ex", role="viewer", password_hash="!")
            db.add(u1)
        u2 = db.query(User).filter_by(tenant_id=tenant_id, email="b@ex").first()
        if not u2:
            u2 = User(tenant_id=tenant_id, email="b@ex", role="editor", password_hash="!")
            db.add(u2)
        db.commit()
        db.refresh(u1)
        db.refresh(u2)
        return u1.id, u2.id
    finally:
        db.close()


def test_users_patch_validation_duplicate_and_happy_path(client_admin):
    u1_id, u2_id = _seed_two_users(tenant_id=1)
    assert u1_id is not None and u2_id is not None

    # Prime CSRF for admin
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "p1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "p1"}

    # invalid email format
    r1 = client_admin.patch(f"/admin/users/{u1_id}", json={"email": "x"}, headers=headers)
    assert r1.status_code == 422
    body1 = r1.get_json()
    assert body1.get("error") in ("invalid", "validation_error", "invalid")
    reasons1 = [p.get("reason") for p in body1.get("invalid_params", []) if p.get("name") == "email"]
    assert "invalid_format" in reasons1

    # invalid role enum
    r2 = client_admin.patch(f"/admin/users/{u1_id}", json={"role": "invalid"}, headers=headers)
    assert r2.status_code == 422
    body2 = r2.get_json()
    reasons2 = [p.get("reason") for p in body2.get("invalid_params", []) if p.get("name") == "role"]
    assert "invalid_enum" in reasons2

    # duplicate email within tenant (u2 has b@ex)
    r3 = client_admin.patch(f"/admin/users/{u1_id}", json={"email": "b@ex"}, headers=headers)
    assert r3.status_code == 422
    body3 = r3.get_json()
    reasons3 = [p.get("reason") for p in body3.get("invalid_params", []) if p.get("name") == "email"]
    assert "duplicate" in reasons3

    # role update (idempotent OK regardless of prior state)
    r4 = client_admin.patch(f"/admin/users/{u1_id}", json={"role": "editor"}, headers=headers)
    assert r4.status_code == 200
    body4 = r4.get_json()
    assert set(body4.keys()) >= {"id", "email", "role", "updated_at"}
    assert body4["role"] == "editor"

    # email update persists with updated_at present
    r5 = client_admin.patch(f"/admin/users/{u1_id}", json={"email": "a2@ex"}, headers=headers)
    assert r5.status_code == 200
    body5 = r5.get_json()
    assert set(body5.keys()) >= {"id", "email", "role", "updated_at"}
    assert body5["email"] == "a2@ex"
    assert isinstance(body5.get("updated_at"), str) and len(body5["updated_at"]) > 0
