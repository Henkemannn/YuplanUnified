from __future__ import annotations

from collections.abc import Mapping

from core import deprecation_warn as dw
from core.metrics import set_metrics


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str,str]]] = []
    def increment(self, name: str, tags: Mapping[str,str] | None = None) -> None:
        self.calls.append((name, dict(tags or {})))

def test_cook_warn_once_per_tenant_day(monkeypatch, client_admin, caplog):
    monkeypatch.setenv("LEGACY_COOK_WARN", "true")
    # fresh limiter
    dw.set_warn_limiter(dw.InProcessWarnLimiter())
    rec = _Recorder(); set_metrics(rec)
    caplog.set_level("WARNING")
    # enable flag so cook creation passes
    client_admin.post("/features/set", json={"name": "allow_legacy_cook_create", "enabled": True}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    # first create
    r1 = client_admin.post("/tasks/", json={"title": "A"}, headers={"X-User-Role":"cook","X-Tenant-Id":"1"})
    assert r1.status_code in (200,201)
    # second create same day
    r2 = client_admin.post("/tasks/", json={"title": "B"}, headers={"X-User-Role":"cook","X-Tenant-Id":"1"})
    assert r2.status_code in (200,201)
    warnings = [rec for rec in caplog.records if "deprecated_legacy_cook_create" in rec.message]
    assert len(warnings) == 1, warnings
    # metric tags last call contains deprecated="soon"
    cook_calls = [t for n,t in rec.calls if n == "tasks.create.legacy_cook"]
    assert cook_calls, "expected metric calls"
    assert any(c.get("deprecated") == "soon" for c in cook_calls)

def test_viewer_no_warn(monkeypatch, client_admin, caplog):
    monkeypatch.setenv("LEGACY_COOK_WARN", "true")
    dw.set_warn_limiter(dw.InProcessWarnLimiter())
    rec = _Recorder(); set_metrics(rec)
    caplog.set_level("WARNING")
    r = client_admin.post("/tasks/", json={"title": "V"}, headers={"X-User-Role":"viewer","X-Tenant-Id":"1"})
    assert r.status_code == 403
    warnings = [rec for rec in caplog.records if "deprecated_legacy_cook_create" in rec.message]
    assert not warnings
    # ensure no deprecated tag (viewer blocked so no increment path executed)
    cook_calls = [t for n,t in rec.calls if n == "tasks.create.legacy_cook"]
    assert not any(c.get("deprecated") == "soon" for c in cook_calls)
