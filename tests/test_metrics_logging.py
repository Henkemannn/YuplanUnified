from __future__ import annotations

from core.metrics import set_metrics
from core.metrics_logging import LoggingMetrics


def _enable_logging_backend(app):
    set_metrics(LoggingMetrics())
    app.config["METRICS_BACKEND"] = "log"


def test_metrics_logging_cook(client_admin, caplog):
    caplog.set_level("INFO", logger="metrics")
    _enable_logging_backend(client_admin.application)
    resp = client_admin.post("/tasks/", json={"title": "Cook metric"}, headers={"X-User-Role":"cook","X-Tenant-Id":"1"})
    assert resp.status_code in (200,201)
    # Look for log line
    lines = [r.message for r in caplog.records if r.name == "metrics"]
    assert any("tasks.create.legacy_cook" in ln for ln in lines), lines
    # Optional: verify some tags pattern
    m = next((ln for ln in lines if "tasks.create.legacy_cook" in ln), "")
    assert "tenant_id" in m
    assert "role" in m
    assert "cook" in m


def test_metrics_logging_viewer_denied(client_admin, caplog):
    caplog.set_level("INFO", logger="metrics")
    _enable_logging_backend(client_admin.application)
    resp = client_admin.post("/tasks/", json={"title": "Viewer denied"}, headers={"X-User-Role":"viewer","X-Tenant-Id":"1"})
    assert resp.status_code == 403
    lines = [r.message for r in caplog.records if r.name == "metrics"]
    assert not any("tasks.create.legacy_cook" in ln for ln in lines)
