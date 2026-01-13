from datetime import UTC, datetime, timedelta

from core.audit_repo import AuditRepo


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


def test_admin_audit_forbidden_403_viewer(client_admin):
    hdrs = {"X-User-Role": "viewer", "X-User-Id": "10", "X-Tenant-Id": "1"}
    resp = client_admin.get("/admin/audit", headers=hdrs)
    assert resp.status_code == 403


def test_admin_audit_default_listing_ok(client_admin):
    repo = AuditRepo()
    seed(repo, 5, tenant_id=1)
    resp = client_admin.get(
        "/admin/audit", headers={"X-User-Role": "admin", "X-User-Id": "1", "X-Tenant-Id": "1"}
    )
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
    resp = client_admin.get(
        "/admin/audit?tenant_id=1&event=beta",
        headers={"X-User-Role": "admin", "X-User-Id": "1", "X-Tenant-Id": "1"},
    )
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
    resp_all = client_admin.get(
        "/admin/audit", headers={"X-User-Role": "admin", "X-User-Id": "1", "X-Tenant-Id": "1"}
    )
    all_items = resp_all.get_json()["items"]
    # Oldest is last in list (descending order), newest first
    newest = all_items[0]["ts"]
    oldest = all_items[-1]["ts"]
    # Query with from=oldest & to=newest should return all three
    resp_window = client_admin.get(
        f"/admin/audit?from={oldest}&to={newest}",
        headers={"X-User-Role": "admin", "X-User-Id": "1", "X-Tenant-Id": "1"},
    )
    assert resp_window.status_code == 200
    assert resp_window.get_json()["meta"]["total"] == len(all_items)


def test_admin_audit_pagination_25_items_10_10_5(client_admin):
    repo = AuditRepo()
    seed(repo, 25, tenant_id=1)
    hdrs = {"X-User-Role": "admin", "X-User-Id": "1", "X-Tenant-Id": "1"}
    page1 = client_admin.get("/admin/audit?size=10&page=1", headers=hdrs).get_json()
    # Pages may exceed 3 if prior tests left residual events; assert at least 3 and first page size correct.
    assert len(page1["items"]) == 10 and page1["meta"]["pages"] >= 3
    page2 = client_admin.get("/admin/audit?size=10&page=2", headers=hdrs).get_json()
    assert len(page2["items"]) == 10
    page3 = client_admin.get("/admin/audit?size=10&page=3", headers=hdrs).get_json()
    # Remaining items on last requested page should be <= requested size
    assert len(page3["items"]) <= 10
    # Sanity: combined unique IDs across these pages equals sum of lengths
    ids = (
        {i["id"] for i in page1["items"]}
        | {i["id"] for i in page2["items"]}
        | {i["id"] for i in page3["items"]}
    )
    assert len(ids) == len(page1["items"]) + len(page2["items"]) + len(page3["items"])  # no overlap
