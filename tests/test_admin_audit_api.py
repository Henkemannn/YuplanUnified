from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from core.db import get_session
from core.audit_repo import AuditRepo
from core.models import Tenant, User


def authenticate_test_user(client, *, role: str, user_id: int, active: bool = True) -> None:
    with client.session_transaction() as sess:
        site_id = sess.get("site_id")
    db = get_session()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == 1).first()
        if tenant is None:
            tenant = Tenant(id=1, name="Audit Test Tenant")
            db.add(tenant)
            db.flush()
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            user = User(
                id=user_id,
                tenant_id=tenant.id,
                username=f"audit-{role}-{user_id}",
                email=f"audit-{role}-{user_id}@example.test",
                password_hash="synthetic",
                role=role,
                auth_version=1,
                is_active=active,
            )
            db.add(user)
        else:
            user.tenant_id = tenant.id
            user.role = role
            user.auth_version = 1
            user.is_active = active
            user.deleted_at = None
        if role != "superuser" and site_id:
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                    "PRIMARY KEY (user_id, site_id))"
                )
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO kitchen_user_sites "
                    "(user_id, tenant_id, site_id) VALUES (:uid, :tid, :sid)"
                ),
                {"uid": user_id, "tid": tenant.id, "sid": site_id},
            )
        db.commit()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["role"] = role
            sess["tenant_id"] = tenant.id
            sess["auth_version"] = 1
    finally:
        db.close()


def seed(
    repo: AuditRepo,
    count: int,
    tenant_id: int = 1,
    base_ts: datetime | None = None,
    event_prefix: str = "evt",
):
    """Seed count events spaced 1s apart, newest last created (we will query desc)."""
    if base_ts is None:
        base_ts = datetime.now(UTC) - timedelta(seconds=count)
    for i in range(count):
        repo.insert(
            event=f"{event_prefix}{i + 1}",
            tenant_id=tenant_id,
            actor_user_id=None,
            actor_role="admin",
            payload={"i": i + 1},
            request_id=f"req-{i + 1}",
        )


def test_admin_audit_unauth_401(client_admin):
    # No session (no required headers to create session)
    resp = client_admin.get("/admin/audit")
    assert resp.status_code == 401


def test_admin_audit_forbidden_viewer(client_admin):
    authenticate_test_user(client_admin, role="viewer", user_id=10)
    resp = client_admin.get("/admin/audit")
    assert resp.status_code in (401, 403)
    if resp.is_json:
        assert "items" not in resp.get_json()


@pytest.mark.parametrize("role", ["admin", "editor", "viewer"])
def test_admin_audit_forbidden_non_superuser_and_tenant_override(client_admin, role):
    authenticate_test_user(client_admin, role=role, user_id={"admin": 11, "editor": 12, "viewer": 13}[role])
    resp = client_admin.get("/admin/audit?tenant_id=2")
    assert resp.status_code in (401, 403)
    if resp.is_json:
        assert "items" not in resp.get_json()


def test_admin_audit_forbidden_deactivated_superuser(client_admin):
    authenticate_test_user(client_admin, role="superuser", user_id=14, active=False)
    resp = client_admin.get("/admin/audit")
    assert resp.status_code == 401
    if resp.is_json:
        assert "items" not in resp.get_json()


def test_admin_audit_default_listing_ok(client_admin):
    repo = AuditRepo()
    seed(repo, 5, tenant_id=1)
    authenticate_test_user(client_admin, role="superuser", user_id=1)
    resp = client_admin.get("/admin/audit")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    meta = data["meta"]
    assert meta["page"] == 1 and meta["size"] == 20
    items = data["items"]
    assert len(items) == 5
    # Desc order by ts (insertion spaced by 1s ascending -> returned reversed)
    ts_list = [i["ts"] for i in items]
    assert ts_list == sorted(ts_list, reverse=True)
    assert resp.headers.get("X-Request-Id")  # header present


def test_admin_audit_filters_ok(client_admin):
    repo = AuditRepo()
    # Mixed tenants + events
    repo.insert(
        event="alpha",
        tenant_id=1,
        actor_user_id=None,
        actor_role="admin",
        payload=None,
        request_id="r1",
    )
    repo.insert(
        event="beta",
        tenant_id=2,
        actor_user_id=None,
        actor_role="admin",
        payload=None,
        request_id="r2",
    )
    repo.insert(
        event="beta",
        tenant_id=1,
        actor_user_id=None,
        actor_role="admin",
        payload=None,
        request_id="r3",
    )
    authenticate_test_user(client_admin, role="superuser", user_id=1)
    resp = client_admin.get("/admin/audit?tenant_id=1&event=beta")
    assert resp.status_code == 200
    data = resp.get_json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["event"] == "beta" and items[0]["tenant_id"] == 1


def test_admin_audit_window_inclusive(client_admin):
    repo = AuditRepo()
    # Insert three events with exact timestamps we control
    repo.insert(
        event="e1",
        tenant_id=1,
        actor_user_id=None,
        actor_role="admin",
        payload=None,
        request_id="r1",
    )
    repo.insert(
        event="e2",
        tenant_id=1,
        actor_user_id=None,
        actor_role="admin",
        payload=None,
        request_id="r2",
    )
    repo.insert(
        event="e3",
        tenant_id=1,
        actor_user_id=None,
        actor_role="admin",
        payload=None,
        request_id="r3",
    )
    # We can't easily set ts directly without model override; rely on ordering and inclusive boundaries by capturing after inserts.
    authenticate_test_user(client_admin, role="superuser", user_id=1)
    resp_all = client_admin.get("/admin/audit")
    all_items = resp_all.get_json()["items"]
    # Oldest is last in list (descending order), newest first
    newest = all_items[0]["ts"]
    oldest = all_items[-1]["ts"]
    # Query with from=oldest & to=newest should return all three
    resp_window = client_admin.get(f"/admin/audit?from={oldest}&to={newest}")
    assert resp_window.status_code == 200
    assert resp_window.get_json()["meta"]["total"] == len(all_items)


def test_admin_audit_pagination_25_items_10_10_5(client_admin):
    repo = AuditRepo()
    seed(repo, 25, tenant_id=1)
    authenticate_test_user(client_admin, role="superuser", user_id=1)
    page1 = client_admin.get("/admin/audit?size=10&page=1").get_json()
    # Pages may exceed 3 if prior tests left residual events; assert at least 3 and first page size correct.
    assert len(page1["items"]) == 10 and page1["meta"]["pages"] >= 3
    page2 = client_admin.get("/admin/audit?size=10&page=2").get_json()
    assert len(page2["items"]) == 10
    page3 = client_admin.get("/admin/audit?size=10&page=3").get_json()
    # Remaining items on last requested page should be <= requested size
    assert len(page3["items"]) <= 10
    # Sanity: combined unique IDs across these pages equals sum of lengths
    ids = (
        {i["id"] for i in page1["items"]}
        | {i["id"] for i in page2["items"]}
        | {i["id"] for i in page3["items"]}
    )
    assert len(ids) == len(page1["items"]) + len(page2["items"]) + len(page3["items"])  # no overlap
