from __future__ import annotations

import hashlib

from core.db import get_session
from core.models import User

from ._problem_utils import assert_problem


def _seed_two_users(tenant_id: int = 1):
    db = get_session()
    try:
        u1 = db.query(User).filter_by(tenant_id=tenant_id, email="pua@ex").first()
        if not u1:
            u1 = User(tenant_id=tenant_id, email="pua@ex", role="viewer", password_hash="!")
            db.add(u1)
        u2 = db.query(User).filter_by(tenant_id=tenant_id, email="pub@ex").first()
        if not u2:
            u2 = User(tenant_id=tenant_id, email="pub@ex", role="editor", password_hash="!")
            db.add(u2)
        db.commit()
        db.refresh(u1)
        db.refresh(u2)
        return u1.id, u2.id
    finally:
        db.close()


def test_users_put_validation_and_happy_path(client_admin):
    u1_id, u2_id = _seed_two_users(tenant_id=1)
    assert u1_id is not None and u2_id is not None

    # Prime CSRF for admin
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "put1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "put1"}

    # missing required fields
    r_missing = client_admin.put(f"/admin/users/{u1_id}", json={}, headers=headers)
    body_m = assert_problem(r_missing, 422, "Validation error")
    names_m = [p.get("name") for p in body_m.get("invalid_params", [])]
    assert "email" in names_m and "role" in names_m

    # invalid email format
    r_email = client_admin.put(f"/admin/users/{u1_id}", json={"email": "x", "role": "viewer"}, headers=headers)
    body_e = assert_problem(r_email, 422, "Validation error")
    reasons_e = [p.get("reason") for p in body_e.get("invalid_params", []) if p.get("name") == "email"]
    assert "invalid_format" in reasons_e

    # invalid role enum
    r_role = client_admin.put(f"/admin/users/{u1_id}", json={"email": "ok@ex", "role": "invalid"}, headers=headers)
    body_r = assert_problem(r_role, 422, "Validation error")
    reasons_r = [p.get("reason") for p in body_r.get("invalid_params", []) if p.get("name") == "role"]
    assert "invalid_enum" in reasons_r

    # additional property not allowed
    r_extra = client_admin.put(
        f"/admin/users/{u1_id}", json={"email": "ok@ex", "role": "viewer", "extra": True}, headers=headers
    )
    body_x = assert_problem(r_extra, 422, "Validation error")
    names_x = [p.get("name") for p in body_x.get("invalid_params", [])]
    assert "extra" in names_x

    # duplicate email within tenant (u2 has pub@ex)
    r_dup = client_admin.put(
        f"/admin/users/{u1_id}", json={"email": "pub@ex", "role": "viewer"}, headers=headers
    )
    body_d = assert_problem(r_dup, 422, "Validation error")
    reasons_d = [p.get("reason") for p in body_d.get("invalid_params", []) if p.get("name") == "email"]
    assert "duplicate" in reasons_d

    # happy path: update both fields
    # Include If-Match for actual change
    db = get_session()
    try:
        row = db.query(User).filter_by(id=u1_id).first()
        ts = getattr(row, "updated_at", None)
        ts_iso = ts.isoformat() if ts is not None else ""
        etag = 'W/"' + hashlib.sha1(f"{u1_id}:{ts_iso}".encode()).hexdigest() + '"'
    finally:
        db.close()
    headers2 = dict(headers)
    headers2["If-Match"] = etag
    r_ok = client_admin.put(
        f"/admin/users/{u1_id}", json={"email": "pu_new@ex", "role": "editor"}, headers=headers2
    )
    assert r_ok.status_code == 200
    body_ok = r_ok.get_json()
    assert set(body_ok.keys()) >= {"id", "email", "role", "updated_at"}
    assert body_ok["email"] == "pu_new@ex"
    assert body_ok["role"] == "editor"
    assert isinstance(body_ok.get("updated_at"), str) and len(body_ok["updated_at"]) > 0


def test_users_put_not_found_returns_404(client_admin):
    # Prime CSRF for admin
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "put2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "put2"}

    r = client_admin.put("/admin/users/9999999", json={"email": "x@ex", "role": "viewer"}, headers=headers)
    assert_problem(r, 404, "Not Found")
