from __future__ import annotations

from core.db import get_session
from core.models import User

from ._problem_utils import assert_problem


audit_calls = []

def _spy_audit(name: str, **fields):
    audit_calls.append((name, fields))


def _seed_user(tenant_id: int = 1, email: str = "email_a@ex", role: str = "viewer"):
    db = get_session()
    try:
        u = db.query(User).filter_by(tenant_id=tenant_id, email=email).first()
        if not u:
            u = User(tenant_id=tenant_id, email=email, role=role, password_hash="!")
            db.add(u)
            db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def test_audit_emitted_only_on_actual_email_change(monkeypatch, client_admin):
    global audit_calls
    audit_calls = []

    # Spy the audit helper; prefer .log, fallback to .log_event
    import core.audit as audit_mod
    if hasattr(audit_mod, "log"):
        monkeypatch.setattr(audit_mod, "log", _spy_audit, raising=True)
    else:
        monkeypatch.setattr(audit_mod, "log_event", _spy_audit, raising=True)

    # Arrange admin + CSRF
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "e1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "e1"}

    # Seed two users
    u1_id = _seed_user(tenant_id=1, email="email_a@ex", role="viewer")
    _ = _seed_user(tenant_id=1, email="email_b@ex", role="viewer")

    # PATCH same email -> no event
    r1 = client_admin.patch(f"/admin/users/{u1_id}", json={"email": "email_a@ex"}, headers=headers)
    assert r1.status_code == 200
    assert len([c for c in audit_calls if c[0] == "user_update_email"]) == 0

    # PATCH new email -> one event with old/new
    r2 = client_admin.patch(f"/admin/users/{u1_id}", json={"email": "email_a2@ex"}, headers=headers)
    assert r2.status_code == 200
    upd_events = [c for c in audit_calls if c[0] == "user_update_email"]
    assert len(upd_events) >= 1
    evt = upd_events[-1]
    assert evt[1].get("old_email") == "email_a@ex"
    assert evt[1].get("new_email") == "email_a2@ex"

    # PUT same email/role -> no additional event
    r3 = client_admin.put(
        f"/admin/users/{u1_id}", json={"email": "email_a2@ex", "role": "viewer"}, headers=headers
    )
    assert r3.status_code == 200
    after_count = len([c for c in audit_calls if c[0] == "user_update_email"])

    # PUT update email -> one more event
    r4 = client_admin.put(
        f"/admin/users/{u1_id}", json={"email": "email_a3@ex", "role": "viewer"}, headers=headers
    )
    assert r4.status_code == 200
    final_count = len([c for c in audit_calls if c[0] == "user_update_email"])
    assert final_count == after_count + 1
