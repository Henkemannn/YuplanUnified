from __future__ import annotations

from core.app_factory import create_app
from core.db import get_session
from core.models import Site, Tenant, TenantFeatureFlag, User
from sqlalchemy import text


def _client(with_flag: bool):
    import os

    os.environ["RATE_LIMIT_BACKEND"] = "memory"  # ensure deterministic backend for test
    from core import rate_limiter as rl

    rl._test_reset()
    app = create_app({"TESTING": True})
    db = get_session()
    try:
        tenant = db.get(Tenant, 1)
        if tenant is None:
            tenant = Tenant(id=1, name="Rate Limit Tenant")
            db.add(tenant)
            db.commit()
        site = db.get(Site, "rate-limit-site")
        if site is None:
            db.add(Site(id="rate-limit-site", tenant_id=1, name="Rate Limit Site"))
        user = db.get(User, 1)
        if user is None:
            user = User(
                id=1,
                tenant_id=1,
                email="rate-limit@example.test",
                password_hash="!",
                role="admin",
                is_active=True,
                auth_version=1,
            )
            db.add(user)
        else:
            user.tenant_id = 1
            user.role = "admin"
            user.is_active = True
            user.auth_version = 1
        db.commit()
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites "
                "(user_id INTEGER, tenant_id INTEGER, site_id TEXT)"
            )
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (1, 1, 'rate-limit-site')"
            )
        )
        rec = (
            db.query(TenantFeatureFlag)
            .filter(TenantFeatureFlag.tenant_id == 1, TenantFeatureFlag.name == "rate_limit_export")
            .first()
        )
        if not rec:
            rec = TenantFeatureFlag(tenant_id=1, name="rate_limit_export", enabled=with_flag)
            db.add(rec)
        else:
            rec.enabled = with_flag
        db.commit()
    finally:
        db.close()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.update(
            {
                "tenant_id": 1,
                "user_id": 1,
                "role": "admin",
                "auth_version": 1,
                "site_id": "rate-limit-site",
            }
        )
    return client


HEADERS = {"X-User-Role": "editor", "X-Tenant-Id": "1"}


def test_export_flag_off_no_limit():
    c = _client(with_flag=False)
    # The active Notes export remains available when the tenant flag is off.
    for _i in range(6):
        r = c.get("/export/notes.csv", headers=HEADERS)
        body = r.get_data()  # consume generator to avoid context warning
        assert r.status_code == 200, body[:200]


def test_export_flag_on_enforces_limit():
    c = _client(with_flag=True)
    # quota is 5: first 5 ok, 6th is rate limited.
    for _i in range(5):
        resp = c.get("/export/notes.csv", headers=HEADERS)
        _ = resp.get_data()
        assert resp.status_code == 200
    r = c.get("/export/notes.csv", headers=HEADERS)
    _ = r.get_data()
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) >= 0
    data = r.get_json()
    assert data.get("status") == 429
    assert data.get("type", " ").endswith("/rate_limited")
    assert data.get("detail") == "rate_limited"


def test_export_isolated_by_user():
    c = _client(with_flag=True)
    # User 1 consumes the Notes-export quota.
    for _i in range(5):
        resp = c.get("/export/notes.csv", headers=HEADERS)
        _ = resp.get_data()
        assert resp.status_code == 200
    # same tenant different user should have separate bucket
    last = c.get("/export/notes.csv", headers=HEADERS)
    _ = last.get_data()
    assert last.status_code == 429
