from core import metrics as metrics_mod
from core.app_factory import create_app


class Recorder:
    def __init__(self):
        self.calls = []

    def increment(self, name: str, tags=None):  # pragma: no cover simple recorder
        self.calls.append((name, dict(tags or {})))


def test_upsert_emits_metric(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(metrics_mod, "increment", rec.increment)
    app = create_app({"TESTING": True})
    c = app.test_client()
    c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 1, "name": "exp", "quota": 5, "per_seconds": 60},
    )
    # Expect at least one increment with name admin.limits.upsert
    assert any(n == "admin.limits.upsert" for n, _ in rec.calls)
    up = [tags for n, tags in rec.calls if n == "admin.limits.upsert"][-1]
    assert up["tenant_id"] == "1" and up["name"] == "exp"
    assert up["updated"] in ("true", "false")


def test_delete_emits_metric(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(metrics_mod, "increment", rec.increment)
    app = create_app({"TESTING": True})
    c = app.test_client()
    # create then delete
    c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 2, "name": "exp", "quota": 5, "per_seconds": 60},
    )
    c.delete(
        "/admin/limits", headers={"X-User-Role": "admin"}, json={"tenant_id": 2, "name": "exp"}
    )
    assert any(n == "admin.limits.delete" for n, _ in rec.calls)
    dl = [tags for n, tags in rec.calls if n == "admin.limits.delete"][-1]
    assert dl["tenant_id"] == "2" and dl["name"] == "exp"
    assert dl["removed"] in ("true", "false")
