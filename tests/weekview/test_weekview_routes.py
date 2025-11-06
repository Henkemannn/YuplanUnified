import re
import uuid


ETAG_RE = re.compile(r'^W/"weekview:dept:.*:year:\d{4}:week:\d{1,2}:v\d+"$')


def _enable_flag(app, name: str, enabled: bool):
    reg = getattr(app, "feature_registry")
    # Ensure exists
    try:
        reg.add(name)
    except Exception:
        pass
    reg.set(name, enabled)


def test_feature_flag_off_returns_404(client_admin):
    app = client_admin.application
    _enable_flag(app, "ff.weekview.enabled", False)

    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

    r = client_admin.get("/api/weekview?year=2025&week=44", headers=headers)
    assert r.status_code == 404

    r = client_admin.get(
        f"/api/weekview/resolve?site=main&department_id={uuid.uuid4()}&date=2025-11-06",
        headers=headers,
    )
    assert r.status_code == 404

    r = client_admin.patch("/api/weekview", headers=headers, json={})
    assert r.status_code == 404


def test_weekview_get_and_resolve_etag_and_rbac(client_admin):
    app = client_admin.application
    _enable_flag(app, "ff.weekview.enabled", True)

    dep_id = str(uuid.uuid4())
    base_headers = {"X-Tenant-Id": "1"}

    for role in ("admin", "editor", "viewer"):
        h = {**base_headers, "X-User-Role": role}
        r = client_admin.get(f"/api/weekview?year=2025&week=44&department_id={dep_id}", headers=h)
        assert r.status_code == 200, role
        assert "ETag" in r.headers
        assert ETAG_RE.match(r.headers["ETag"]) is not None
        data = r.get_json()
        assert isinstance(data, dict)
        assert data.get("year") == 2025
        assert data.get("week") == 44
        assert isinstance(data.get("department_summaries"), list)

        r2 = client_admin.get(
            f"/api/weekview/resolve?site=main&department_id={dep_id}&date=2025-11-06",
            headers=h,
        )
        assert r2.status_code == 200, role


def test_weekview_patch_rbac_and_if_match(client_admin):
    app = client_admin.application
    _enable_flag(app, "ff.weekview.enabled", True)

    base_headers = {"X-Tenant-Id": "1"}

    # viewer forbidden
    r = client_admin.patch("/api/weekview", headers={**base_headers, "X-User-Role": "viewer"})
    assert r.status_code == 403

    # admin/editor must provide If-Match
    for role in ("admin", "editor"):
        h = {**base_headers, "X-User-Role": role}
        r = client_admin.patch("/api/weekview", headers=h, json={})
        assert r.status_code == 400
        r = client_admin.patch(
            "/api/weekview",
            headers={**h, "If-Match": 'W/"weekview:dept:abc:year:2025:week:44:v0"'},
            json={"ops": []},
        )
        assert r.status_code == 501
import re

import pytest

ETAG_RE = re.compile(r'^W/"weekview:dept:.*:year:\d{4}:week:\d{1,2}:v\d+"$')


@pytest.fixture
def enable_weekview(client_admin):
    # Enable feature flag via admin endpoint
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200


def _get(client, role, path):
    return client.get(path, headers={"X-User-Role": role, "X-Tenant-Id": "1"})


def _patch(client, role, path, json=None, extra_headers=None):
    headers = {"X-User-Role": role, "X-Tenant-Id": "1"}
    if extra_headers:
        headers.update(extra_headers)
    return client.patch(path, json=json or {}, headers=headers)


def test_feature_flag_off_all_404(client_admin):
    # Explicitly disable via admin endpoint to avoid leakage from other tests
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": False},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200
    # Ensure disabled now yields 404
    for path in [
        "/api/weekview?year=2025&week=45",
        "/api/weekview/resolve?site=s1&department_id=00000000-0000-0000-0000-000000000000&date=2025-11-03",
    ]:
        r = _get(client_admin, "admin", path)
        assert r.status_code == 404


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_rbac_and_etag(client_admin):
    base = "/api/weekview?year=2025&week=45&department_id=00000000-0000-0000-0000-000000000000"

    # GET allowed for admin/editor/viewer
    for role in ["admin", "editor", "viewer"]:
        r = _get(client_admin, role, base)
        assert r.status_code == 200
        assert "ETag" in r.headers
        assert ETAG_RE.match(r.headers["ETag"]) is not None

    # GET resolve allowed for all
    r = _get(
        client_admin,
        "viewer",
        "/api/weekview/resolve?site=s1&department_id=00000000-0000-0000-0000-000000000000&date=2025-11-03",
    )
    assert r.status_code == 200

    # PATCH RBAC
    # viewer -> 403
    r = _patch(client_admin, "viewer", "/api/weekview", json={})
    assert r.status_code == 403

    # admin/editor must send If-Match
    r = _patch(client_admin, "admin", "/api/weekview", json={})
    assert r.status_code == 400

    r = _patch(
        client_admin,
        "editor",
        "/api/weekview",
        json={},
        extra_headers={
            "If-Match": 'W/"weekview:dept:00000000-0000-0000-0000-000000000000:year:2025:week:45:v0"',
        },
    )
    assert r.status_code == 501
