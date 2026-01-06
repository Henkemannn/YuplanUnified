import re
import uuid

import pytest

ETAG_RE = re.compile(r'^W/"weekview:dept:[0-9a-f-]+:year:\d{4}:week:\d{1,2}:v\d+"$')


def _get(client, role, path, extra_headers=None):
    headers = {"X-User-Role": role, "X-Tenant-Id": "1"}
    if extra_headers:
        headers.update(extra_headers)
    return client.get(path, headers=headers)


def _patch(client, role, path, json=None, extra_headers=None):
    headers = {"X-User-Role": role, "X-Tenant-Id": "1"}
    if extra_headers:
        headers.update(extra_headers)
    return client.patch(path, json=json or {}, headers=headers)


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200


@pytest.mark.usefixtures("enable_weekview")
def test_conditional_get_304_and_refresh_after_mutation(client_admin):
    dep = str(uuid.uuid4())
    site = str(uuid.uuid4())
    base = f"/api/weekview?year=2025&week=45&department_id={dep}"
    client_admin.post(
        "/ui/select-site",
        data={"site_id": site, "next": "/"},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    r0 = _get(client_admin, "viewer", base)
    assert r0.status_code == 200
    etag0 = r0.headers.get("ETag")
    assert etag0 and ETAG_RE.match(etag0)

    # Conditional GET yields 304 when ETag matches
    r1 = _get(client_admin, "viewer", base, extra_headers={"If-None-Match": etag0})
    assert r1.status_code == 304
    assert r1.headers.get("ETag") == etag0

    # Perform a mutation -> ETag changes
    p = {
        "site_id": site,
        "department_id": dep,
        "year": 2025,
        "week": 45,
        "operations": [{"day_of_week": 1, "meal": "lunch", "diet_type": "normal", "marked": True}],
    }
    r2 = _patch(client_admin, "editor", "/api/weekview", json=p, extra_headers={"If-Match": etag0})
    assert r2.status_code == 200
    etag1 = r2.headers.get("ETag")
    assert etag1 and etag1 != etag0

    # Conditional GET with old ETag should now return 200 with new ETag
    r3 = _get(client_admin, "viewer", base, extra_headers={"If-None-Match": etag0})
    assert r3.status_code == 200
    assert r3.headers.get("ETag") == etag1


@pytest.mark.usefixtures("enable_weekview")
def test_residents_counts_write_and_readback(client_admin):
    dep = str(uuid.uuid4())
    site = str(uuid.uuid4())
    base = f"/api/weekview?year=2025&week=45&department_id={dep}"
    # Align session site context with our test site
    client_admin.post(
        "/ui/select-site",
        data={"site_id": site, "next": "/"},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    etag0 = _get(client_admin, "admin", base).headers.get("ETag")

    payload = {
        "site_id": site,
        "department_id": dep,
        "year": 2025,
        "week": 45,
        "items": [
            {"day_of_week": 1, "meal": "lunch", "count": 12},
            {"day_of_week": 2, "meal": "dinner", "count": 7},
        ],
    }
    r = _patch(client_admin, "admin", "/api/weekview/residents", json=payload, extra_headers={"If-Match": etag0})
    assert r.status_code == 200
    etag1 = r.headers.get("ETag")
    assert etag1 and ETAG_RE.match(etag1)

    data = _get(client_admin, "viewer", base).get_json()
    dep_summ = data["department_summaries"][0]
    counts = {(c["day_of_week"], c["meal"]): c["count"] for c in dep_summ.get("residents_counts", [])}
    assert counts.get((1, "lunch")) == 12
    assert counts.get((2, "dinner")) == 7


@pytest.mark.usefixtures("enable_weekview")
def test_alt2_flags_write_and_clear(client_admin):
    dep = str(uuid.uuid4())
    site = str(uuid.uuid4())
    base = f"/api/weekview?year=2025&week=45&department_id={dep}"
    # Align session site context with our test site
    client_admin.post(
        "/ui/select-site",
        data={"site_id": site, "next": "/"},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    etag0 = _get(client_admin, "admin", base).headers.get("ETag")

    p1 = {"site_id": site, "department_id": dep, "year": 2025, "week": 45, "days": [2, 5]}
    r1 = _patch(client_admin, "editor", "/api/weekview/alt2", json=p1, extra_headers={"If-Match": etag0})
    assert r1.status_code == 200
    etag1 = r1.headers.get("ETag")
    assert etag1 and ETAG_RE.match(etag1)

    d1 = _get(client_admin, "viewer", base).get_json()
    alt2_days = d1["department_summaries"][0].get("alt2_days", [])
    assert sorted(alt2_days) == [2, 5]

    # Clear all
    r2 = _patch(client_admin, "editor", "/api/weekview/alt2", json={**p1, "days": []}, extra_headers={"If-Match": etag1})
    assert r2.status_code == 200
    d2 = _get(client_admin, "viewer", base).get_json()
    assert d2["department_summaries"][0].get("alt2_days", []) == []


@pytest.mark.usefixtures("enable_weekview")
@pytest.mark.parametrize("meal", ["breakfast", "snack"])  # invalid meals
def test_validation_errors_new_endpoints(client_admin, meal):
    dep = str(uuid.uuid4())
    base = f"/api/weekview?year=2025&week=45&department_id={dep}"
    etag0 = _get(client_admin, "admin", base).headers.get("ETag")

    # residents: invalid meal
    p_bad_meal = {"department_id": dep, "year": 2025, "week": 45, "items": [{"day_of_week": 1, "meal": meal, "count": 1}]}
    r1 = _patch(client_admin, "admin", "/api/weekview/residents", json=p_bad_meal, extra_headers={"If-Match": etag0})
    assert r1.status_code == 400

    # residents: negative count
    p_bad_cnt = {"department_id": dep, "year": 2025, "week": 45, "items": [{"day_of_week": 1, "meal": "lunch", "count": -1}]}
    r2 = _patch(client_admin, "admin", "/api/weekview/residents", json=p_bad_cnt, extra_headers={"If-Match": etag0})
    assert r2.status_code == 400

    # alt2: out of range day
    p_bad_day = {"department_id": dep, "year": 2025, "week": 45, "days": [0, 8]}
    r3 = _patch(client_admin, "admin", "/api/weekview/alt2", json=p_bad_day, extra_headers={"If-Match": etag0})
    assert r3.status_code == 400
