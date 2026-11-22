from __future__ import annotations

from collections.abc import Mapping

from core import metrics as metrics_mod


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, str] | None]] = []

    def increment(self, name: str, tags: Mapping[str, str] | None = None) -> None:
        self.calls.append((name, dict(tags or {})))


def test_legacy_cook_create_increments_metric(client_admin):
    rec = _Recorder()
    metrics_mod.set_metrics(rec)
    # enable flag for cook creation
    client_admin.post(
        "/features/set",
        json={"name": "allow_legacy_cook_create", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    resp = client_admin.post(
        "/tasks/",
        json={"title": "Cook can create"},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 404
    assert not any(name == "tasks.create.legacy_cook" for name, _ in rec.calls)


def test_viewer_create_does_not_increment(client_admin):
    rec = _Recorder()
    metrics_mod.set_metrics(rec)
    resp = client_admin.post(
        "/tasks/",
        json={"title": "Viewer blocked"},
        headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 404
    assert not any(name == "tasks.create.legacy_cook" for name, _ in rec.calls)
