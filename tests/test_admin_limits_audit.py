from core.app_factory import create_app


class AuditRecorder:
    def __init__(self):
        self.events = []

    def log_event(self, name: str, **payload):  # pragma: no cover simple
        self.events.append((name, payload))


def test_upsert_audited(monkeypatch):
    from core import admin_api as mod

    rec = AuditRecorder()
    monkeypatch.setattr(mod, "_emit_audit", rec.log_event)
    app = create_app({"TESTING": True})
    c = app.test_client()
    resp = c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 5, "name": "exp", "quota": 9, "per_seconds": 60},
    )
    print("DEBUG upsert status", resp.status_code, resp.json)
    print("DEBUG events after upsert", rec.events)
    ev = [e for e in rec.events if e[0] == "limits_upsert"]
    assert len(ev) == 1
    payload = ev[0][1]
    assert payload["tenant_id"] == 5
    assert payload["limit_name"] == "exp"
    assert payload["quota"] == 9
    assert payload["per_seconds"] == 60
    assert "updated" in payload
    assert "actor_role" in payload and payload["actor_role"] == "admin"


def test_delete_audited(monkeypatch):
    from core import admin_api as mod

    rec = AuditRecorder()
    monkeypatch.setattr(mod, "_emit_audit", rec.log_event)
    app = create_app({"TESTING": True})
    c = app.test_client()
    # create then delete
    resp1 = c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 6, "name": "exp", "quota": 3, "per_seconds": 60},
    )
    resp2 = c.delete(
        "/admin/limits", headers={"X-User-Role": "admin"}, json={"tenant_id": 6, "name": "exp"}
    )
    print("DEBUG delete create status", resp1.status_code, resp1.json)
    print("DEBUG delete delete status", resp2.status_code, resp2.json)
    print("DEBUG events after delete flow", rec.events)
    ev = [e for e in rec.events if e[0] == "limits_delete"]
    assert len(ev) == 1
    payload = ev[0][1]
    assert payload["tenant_id"] == 6
    assert payload["limit_name"] == "exp"
    assert "removed" in payload
    assert "actor_role" in payload and payload["actor_role"] == "admin"
