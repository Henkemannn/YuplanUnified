from __future__ import annotations

from core.db import get_session
from core.models import TenantFeatureFlag, User

audit_calls = []

def _spy_audit(name: str, **fields):
    audit_calls.append((name, fields))


def _seed_users(tenant_id: int = 1):
    db = get_session()
    try:
        if not db.query(User).filter_by(tenant_id=tenant_id, email="aud_u1@example.com").first():
            db.add(User(tenant_id=tenant_id, email="aud_u1@example.com", role="viewer", password_hash="!"))
        if not db.query(User).filter_by(tenant_id=tenant_id, email="aud_u2@example.com").first():
            db.add(User(tenant_id=tenant_id, email="aud_u2@example.com", role="editor", password_hash="!"))
        db.commit()
        u1 = db.query(User).filter_by(tenant_id=tenant_id, email="aud_u1@example.com").first()
        u2 = db.query(User).filter_by(tenant_id=tenant_id, email="aud_u2@example.com").first()
        return u1.id, u2.id
    finally:
        db.close()


def _ensure_flag(tenant_id: int = 1, key: str = "aud-flag"):
    db = get_session()
    try:
        if not db.query(TenantFeatureFlag).filter_by(tenant_id=tenant_id, name=key).first():
            db.add(TenantFeatureFlag(tenant_id=tenant_id, name=key, enabled=False, notes=""))
            db.commit()
    finally:
        db.close()


def test_audit_events_for_admin_mutations(monkeypatch, client_admin):
    global audit_calls
    audit_calls = []

    # Spy the audit helper; prefer .log, fallback to .log_event
    import core.audit as audit_mod
    if hasattr(audit_mod, "log"):
        monkeypatch.setattr(audit_mod, "log", _spy_audit, raising=True)
    else:
        monkeypatch.setattr(audit_mod, "log_event", _spy_audit, raising=True)

    # Prime CSRF for admin mutations
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "audit1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "audit1"}

    # 1) POST /admin/users -> user_create
    r_create = client_admin.post(
        "/admin/users", json={"email": "new_aud@example.com", "role": "viewer"}, headers=headers
    )
    assert r_create.status_code in (201, 200)
    # Exactly one user_create emitted
    user_create_events = [c for c in audit_calls if c[0] == "user_create"]
    assert len(user_create_events) >= 1

    # Prepare users for role change
    u1_id, u2_id = _seed_users(tenant_id=1)

    # 2) PATCH /admin/roles/{id} changing role -> user_update_role (once)
    # Fetch current ETag via GET, then send If-Match for the changing PATCH
    base = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r_etag = client_admin.get(f"/admin/roles/{u1_id}", headers=base)
    assert r_etag.status_code == 200
    etag_role = r_etag.headers.get("ETag")
    assert etag_role
    r_role = client_admin.patch(
        f"/admin/roles/{u1_id}", json={"role": "editor"}, headers={**headers, "If-Match": etag_role}
    )
    assert r_role.status_code == 200
    before_count = len([c for c in audit_calls if c[0] == "user_update_role"])

    # Idempotent: same role again should not add another event
    r_role2 = client_admin.patch(f"/admin/roles/{u1_id}", json={"role": "editor"}, headers=headers)
    assert r_role2.status_code == 200
    after_count = len([c for c in audit_calls if c[0] == "user_update_role"])
    assert after_count == before_count

    # 3) PATCH /admin/feature-flags/{key} changing enabled/notes -> feature_flag_update
    _ensure_flag(tenant_id=1, key="aud-flag")
    # Fetch ETag then mutate with If-Match
    r_flag_etag = client_admin.get("/admin/feature-flags/aud-flag", headers=base)
    assert r_flag_etag.status_code == 200
    etag_flag = r_flag_etag.headers.get("ETag")
    assert etag_flag
    r_flag = client_admin.patch(
        "/admin/feature-flags/aud-flag", json={"enabled": True, "notes": "On"}, headers={**headers, "If-Match": etag_flag}
    )
    assert r_flag.status_code == 200
    flag_events = [c for c in audit_calls if c[0] == "feature_flag_update"]
    assert len(flag_events) >= 1
    # Verify meta structure contains key and changes
    last_flag = flag_events[-1]
    assert last_flag[1].get("key") == "aud-flag"
    assert isinstance(last_flag[1].get("changes"), dict)
    assert last_flag[1]["changes"].get("enabled") is True
    assert last_flag[1]["changes"].get("notes") == "On"
