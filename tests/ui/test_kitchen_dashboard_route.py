import pytest

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def test_kitchen_dashboard_route_ok(app_session):
    client = app_session.test_client()
    rv = client.get("/ui/kitchen", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Kök – Översikt" in html or "Veckovy" in html
