from core import admin_api as mod
from core.app_factory import create_app

calls: list[tuple[str, dict]] = []


def recorder(name: str, **payload):
    calls.append((name, payload))


print("orig _emit_audit", getattr(mod, "_emit_audit", None))
mod._emit_audit = recorder  # type: ignore
print("patched _emit_audit", getattr(mod, "_emit_audit", None))

app = create_app({"TESTING": True})
client = app.test_client()
resp = client.post(
    "/admin/limits",
    headers={"X-User-Role": "admin"},
    json={"tenant_id": 5, "name": "exp", "quota": 9, "per_seconds": 60},
)
print("response status", resp.status_code, resp.json)
print("calls captured", calls)
