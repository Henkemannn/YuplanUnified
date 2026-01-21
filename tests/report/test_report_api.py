import re
import uuid

import pytest

ETAG_DEPT_RE = re.compile(r'^W/"report:dept:[0-9a-f-]+:year:\d{4}:week:\d{1,2}:v\d+"$')
ETAG_SITE_RE = re.compile(r'^W/"report:site:year:\d{4}:week:\d{1,2}:v\d+:n\d+"$')


def _headers(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _get(client, role, path, extra_headers=None):
    h = _headers(role)
    if extra_headers:
        h.update(extra_headers)
    return client.get(path, headers=h)


def _patch(client, role, path, json=None, extra_headers=None):
    h = _headers(role)
    if extra_headers:
        h.update(extra_headers)
    return client.patch(path, json=json or {}, headers=h)


@pytest.fixture
def enable_report(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.report.enabled", "enabled": True},
        headers=_headers("admin"),
    )
    assert resp.status_code == 200


def test_feature_flag_off_returns_404(client_admin):
    # Disable explicitly
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.report.enabled", "enabled": False},
        headers=_headers("admin"),
    )
    assert resp.status_code == 200

    r = _get(client_admin, "admin", "/api/report?year=2025&week=45")
    assert r.status_code == 404


@pytest.mark.usefixtures("enable_report")
def test_rbac_etag_and_304_site_aggregate(client_admin):
    base = "/api/report?year=2025&week=45"

    # viewer forbidden
    r_forbidden = _get(client_admin, "viewer", base)
    assert r_forbidden.status_code == 403

    for role in ("admin", "editor"):
        r = _get(client_admin, role, base)
        assert r.status_code == 200
        etag = r.headers.get("ETag")
        assert etag and ETAG_SITE_RE.match(etag)
        # Conditional GET
        r2 = _get(client_admin, role, base, extra_headers={"If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.headers.get("ETag") == etag


@pytest.mark.usefixtures("enable_report")
def test_report_math_and_clamp_with_weekview_data(client_admin):
    # Enable weekview to use its endpoints for data seeding
    client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_headers("admin"),
    )
    dep = str(uuid.uuid4())
    site = str(uuid.uuid4())
    year, week = 2025, 45
    wv_base = f"/api/weekview?year={year}&week={week}&department_id={dep}"
    # Align session site context for weekview mutations (selector is superuser-only)
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site

    # Get initial ETag for weekview
    r0 = _get(client_admin, "admin", wv_base)
    assert r0.status_code == 200
    etag0 = r0.headers.get("ETag")

    # Seed residents counts: lunch d1=10, d2=5
    payload_res = {
        "site_id": site,
        "department_id": dep,
        "year": year,
        "week": week,
        "items": [
            {"day_of_week": 1, "meal": "lunch", "count": 10},
            {"day_of_week": 2, "meal": "lunch", "count": 5},
        ],
    }
    r1 = _patch(
        client_admin,
        "admin",
        "/api/weekview/residents",
        json=payload_res,
        extra_headers={"If-Match": etag0},
    )
    assert r1.status_code == 200
    etag1 = r1.headers.get("ETag")

    # Mark specials: lunch gluten on day1, timbal on day2
    ops = [
        {"day_of_week": 1, "meal": "lunch", "diet_type": "gluten", "marked": True},
        {"day_of_week": 2, "meal": "lunch", "diet_type": "timbal", "marked": True},
    ]
    r2 = _patch(
        client_admin,
        "editor",
        "/api/weekview",
        json={"site_id": site, "department_id": dep, "year": year, "week": week, "operations": ops},
        extra_headers={"If-Match": etag1},
    )
    assert r2.status_code == 200

    # Now fetch report and verify aggregation
    r3 = _get(client_admin, "admin", f"/api/report?year={year}&week={week}&department_id={dep}")
    assert r3.status_code == 200
    data = r3.get_json()
    assert data["year"] == year and data["week"] == week
    dept = data["departments"][0]
    assert dept["department_id"] == dep
    lunch = dept["lunch"]
    assert lunch["specials"].get("gluten") == 1
    assert lunch["specials"].get("timbal") == 1
    # normal = residents_total (10+5) - specials_sum (2)
    assert lunch["normal"] == 13
    assert lunch["total"] == 15


@pytest.mark.usefixtures("enable_report")
def test_report_department_404_when_unknown(client_admin):
    # Unknown department for this week should yield 404
    dep = str(uuid.uuid4())
    r = _get(client_admin, "admin", f"/api/report?year=2025&week=45&department_id={dep}")
    assert r.status_code == 404
