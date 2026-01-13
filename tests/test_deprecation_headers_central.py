from __future__ import annotations

from core import metrics as metrics_mod


def _login_viewer(client):
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 1
        sess["role"] = "viewer"


def test_notes_alias_has_deprecation_headers(client):
    from collections.abc import Mapping

    class _Rec:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str]]] = []

        def increment(self, name: str, tags: Mapping[str, str] | None = None) -> None:  # type: ignore[override]
            self.calls.append((name, dict(tags or {})))

    rec = _Rec()
    metrics_mod.set_metrics(rec)
    _login_viewer(client)
    r = client.get("/notes/")
    assert r.status_code == 200
    assert r.headers.get("Deprecation") == "true"
    assert "GMT" in r.headers.get("Sunset", "")
    assert 'rel="deprecation"' in r.headers.get("Link", "")
    assert r.headers.get("X-Deprecated-Alias") == "notes"
    assert any(
        n == "deprecation.alias.emitted" and c.get("endpoint") == "notes" for n, c in rec.calls
    )


def test_tasks_alias_has_deprecation_headers(client):
    from collections.abc import Mapping

    class _Rec:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str]]] = []

        def increment(self, name: str, tags: Mapping[str, str] | None = None) -> None:  # type: ignore[override]
            self.calls.append((name, dict(tags or {})))

    rec = _Rec()
    metrics_mod.set_metrics(rec)
    _login_viewer(client)
    r = client.get("/tasks/")
    assert r.status_code == 200
    assert r.headers.get("X-Deprecated-Alias") == "tasks"
    assert any(
        n == "deprecation.alias.emitted" and c.get("endpoint") == "tasks" for n, c in rec.calls
    )
