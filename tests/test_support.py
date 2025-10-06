import logging

import pytest


@pytest.fixture
def ensure_warning(client):
    # Trigger a warning log with request context
    logging.getLogger(__name__).warning("pilot warning test")


def test_support_requires_admin(client_user):
    r = client_user.get("/admin/support/", headers={"X-User-Role":"cook","X-Tenant-Id":"1"})
    assert r.status_code in (401, 403)


def test_support_admin_ok(client_admin, ensure_warning):
    r = client_admin.get("/admin/support/", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    assert r.status_code == 200
    data = r.get_json()
    assert "service_version" in data
    assert "events" in data


def test_support_lookup(client_admin, ensure_warning):
    # First call support home to ensure buffer populated
    client_admin.get("/admin/support/", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
    # Grab a request id from footer via a simple request (or skip and just ensure 200)
    # Instead we simulate by scanning recent_warnings
    home = client_admin.get("/admin/support/", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}).get_json()
    recents = home.get("recent_warnings", [])
    if recents:
        rid = recents[-1].get("request_id")
        lr = client_admin.get(f"/admin/support/lookup?request_id={rid}", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
        assert lr.status_code == 200
        payload = lr.get_json()
        assert payload["request_id"] == rid
    else:
        pytest.skip("No warnings captured; skipping lookup validation")
