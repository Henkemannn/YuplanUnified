from __future__ import annotations

from core.metrics import set_metrics
from core.metrics_logging import LoggingMetrics


def _enable_logging_backend(app):
    set_metrics(LoggingMetrics())
    app.config["METRICS_BACKEND"] = "log"


def test_metrics_logging_cook(client_admin, caplog):
    caplog.set_level("INFO", logger="metrics")
    _enable_logging_backend(client_admin.application)
    client_admin.post(
        "/features/set",
        json={"name": "allow_legacy_cook_create", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    resp = client_admin.post(
        "/tasks/",
        json={"title": "Cook metric"},
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 404
    # Look for log line
    lines = [r.message for r in caplog.records if r.name == "metrics"]
    assert not any("tasks.create.legacy_cook" in ln for ln in lines)
    # Optional: verify some tags pattern


def test_metrics_logging_viewer_denied(client_admin, caplog):
    caplog.set_level("INFO", logger="metrics")
    _enable_logging_backend(client_admin.application)
    resp = client_admin.post(
        "/tasks/",
        json={"title": "Viewer denied"},
        headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 404
    lines = [r.message for r in caplog.records if r.name == "metrics"]
    assert not any("tasks.create.legacy_cook" in ln for ln in lines)
