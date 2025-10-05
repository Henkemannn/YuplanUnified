import os

os.environ["RATE_LIMIT_BACKEND"] = "memory"
from core import rate_limiter as _rl
from core.app_factory import create_app
from core.db import get_session
from core.limit_registry import refresh, set_override
from core.models import Tenant, User

# Helper to enable feature flag for tenant

def enable_flag(app, tenant_id: int, flag: str):
    # Ensure tenant exists
    db = get_session()
    try:
        t = db.query(Tenant).filter_by(id=tenant_id).first()
        if not t:
            t = Tenant(id=tenant_id, name=f"t{tenant_id}")  # direct id for simplicity
            db.add(t)
            # basic admin user to satisfy potential auth logic
            u = User(tenant_id=tenant_id, email=f"admin{tenant_id}@x", password_hash="x", role="admin", unit_id=None)
            db.add(u)
            db.commit()
        svc = app.feature_service
        if svc:
            svc.enable(tenant_id, flag)
    finally:
        db.close()


def seed_registry_default():
    refresh({}, {"admin_limits_write": {"quota": 10, "per_seconds": 60}})


def make_client(flag_on: bool = False, tenant_id: int = 1):
    # Ensure fresh memory limiter instance each test invocation
    _rl._test_reset()
    base_cfg = {"TESTING": True}
    app = create_app(base_cfg)
    if flag_on:
        app.config["FEATURE_FLAGS"] = {"rate_limit_admin_limits_write": True}
    seed_registry_default()
    if flag_on:
        enable_flag(app, tenant_id, "rate_limit_admin_limits_write")
    return app.test_client(), app


def do_post(c, tenant_id: int, user_id: int, quota=5):  # minimal upsert
    return c.post("/admin/limits", headers={"X-User-Role":"admin","X-Tenant-Id":str(tenant_id),"X-User-Id":str(user_id)}, json={"tenant_id":tenant_id,"name":"exp","quota":quota,"per_seconds":60})

def do_delete(c, tenant_id: int, user_id: int):
    return c.delete("/admin/limits", headers={"X-User-Role":"admin","X-Tenant-Id":str(tenant_id),"X-User-Id":str(user_id)}, json={"tenant_id":tenant_id,"name":"exp"})


def test_write_limit_flag_off_bypass():
    c, app = make_client(flag_on=False)
    # Inflate quota via tenant override to simulate bypass semantics
    set_override(1, "admin_limits_write", 1000, 60)
    for _i in range(12):
        r1 = do_post(c, 1, 1)
        assert r1.status_code == 200, r1.get_data()
        r2 = do_delete(c, 1, 1)
        assert r2.status_code == 200, r2.get_data()


def test_write_limit_flag_on_enforce():
    c, app = make_client(flag_on=True)
    # Warm with an initial create so delete has target
    for _i in range(10):
        resp = do_post(c, 1, 1)
        assert resp.status_code == 200, resp.get_data()
    # 11th should block
    blocked = do_post(c, 1, 1)
    assert blocked.status_code == 429, blocked.get_data()
    body = blocked.get_json()
    assert body["error"] == "rate_limited"
    assert body["limit"] == "admin_limits_write"
    assert "retry_after" in body
    assert int(blocked.headers.get("Retry-After", "0")) >= 0


def test_write_limit_isolation_per_user():
    c, app = make_client(flag_on=True)
    # User 1 uses full quota
    for _ in range(10):
        assert do_post(c, 1, 1).status_code == 200
    assert do_post(c, 1, 1).status_code == 429  # blocked for user 1
    # User 2 still allowed fresh quota
    for _ in range(10):
        assert do_post(c, 1, 2).status_code == 200
    assert do_post(c, 1, 2).status_code == 429


def test_write_limit_lookup_metric_emitted(monkeypatch):
    hits = []
    from core import limit_registry as reg
    orig = reg.metrics_mod.increment
    def capture(name, tags=None):  # type: ignore[override]
        if name == "rate_limit.lookup" and tags and tags.get("name") == "admin_limits_write":
            hits.append(tags.get("source"))
        return orig(name, tags)
    monkeypatch.setattr(reg.metrics_mod, "increment", capture)
    c, app = make_client(flag_on=True)
    for _ in range(2):
        do_post(c, 1, 1)
    # At least one lookup recorded
    assert any(src in ("default","tenant","fallback") for src in hits)
