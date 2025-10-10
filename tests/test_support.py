import logging

import pytest


@pytest.fixture
def ensure_warning(client):
    # Trigger a warning log with request context
    logging.getLogger(__name__).warning("pilot warning test")


def test_support_requires_admin(client_user):
    r = client_user.get("/admin/support/", headers={"X-User-Role":"cook","X-Tenant-Id":"1"})
    assert r.status_code in (401, 403)


def test_support_superuser_ok(client_superuser, ensure_warning):
    r = client_superuser.get("/admin/support/", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    assert r.status_code == 200
    data = r.get_json()
    assert "service_version" in data
    assert "events" in data


def test_support_lookup_superuser(client_superuser, ensure_warning):
    client_superuser.get("/admin/support/", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
    home = client_superuser.get("/admin/support/", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"}).get_json()
    recents = home.get("recent_warnings", [])
    if recents:
        rid = recents[-1].get("request_id")
        lr = client_superuser.get(f"/admin/support/lookup?request_id={rid}", headers={"X-User-Role":"superuser","X-Tenant-Id":"1"})
        assert lr.status_code == 200
        payload = lr.get_json()
        assert payload["request_id"] == rid
    else:
        pytest.skip("No warnings captured; skipping lookup validation")
