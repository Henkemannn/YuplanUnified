import csv
import io
import re
import uuid

import pytest

ETAG_SITE_RE = re.compile(r'^W/"report:site:year:\d{4}:week:\d{1,2}:v\d+:n\d+"$')
ETAG_SITE_CSV_RE = re.compile(r'^W/"report:site:year:\d{4}:week:\d{1,2}:v\d+:n\d+:fmt:csv"$')
ETAG_SITE_XLSX_RE = re.compile(r'^W/"report:site:year:\d{4}:week:\d{1,2}:v\d+:n\d+:fmt:xlsx"$')


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


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_headers("admin"),
    )
    assert resp.status_code == 200


@pytest.mark.usefixtures("enable_report", "enable_weekview")
def test_rbac_and_validation(client_admin):
    base = "/api/report/export?year=2025&week=45&format=csv"
    # viewer forbidden
    r = _get(client_admin, "viewer", base)
    assert r.status_code == 403
    # invalid format
    r2 = _get(client_admin, "admin", "/api/report/export?year=2025&week=45&format=pdf")
    assert r2.status_code == 400
    # invalid week
    r3 = _get(client_admin, "admin", "/api/report/export?year=2025&week=99&format=csv")
    assert r3.status_code == 400


@pytest.mark.usefixtures("enable_report", "enable_weekview")
def test_csv_and_xlsx_export_with_etag_and_304(client_admin):
    dep = str(uuid.uuid4())
    year, week = 2025, 45
    wv_base = f"/api/weekview?year={year}&week={week}&department_id={dep}"

    # Seed weekview: get ETag, set residents and specials
    etag0 = _get(client_admin, "admin", wv_base).headers.get("ETag")
    # residents
    _patch(
        client_admin,
        "admin",
        "/api/weekview/residents",
        json={
            "department_id": dep,
            "year": year,
            "week": week,
            "items": [
                {"day_of_week": 1, "meal": "lunch", "count": 10},
                {"day_of_week": 1, "meal": "dinner", "count": 8},
            ],
        },
        extra_headers={"If-Match": etag0},
    )
    # marks
    etag1 = _get(client_admin, "admin", wv_base).headers.get("ETag")
    _patch(
        client_admin,
        "editor",
        "/api/weekview",
        json={
            "department_id": dep,
            "year": year,
            "week": week,
            "operations": [
                {"day_of_week": 1, "meal": "lunch", "diet_type": "gluten", "marked": True}
            ],
        },
        extra_headers={"If-Match": etag1},
    )

    # Get base report ETag
    r0 = _get(client_admin, "admin", f"/api/report?year={year}&week={week}")
    assert r0.status_code == 200
    base_etag = r0.headers.get("ETag")
    assert base_etag and ETAG_SITE_RE.match(base_etag)

    # CSV export
    rcsv = _get(client_admin, "admin", f"/api/report/export?year={year}&week={week}&format=csv")
    assert rcsv.status_code == 200
    assert rcsv.headers.get("Content-Type", "").startswith("text/csv")
    etcsv = rcsv.headers.get("ETag")
    assert etcsv and ETAG_SITE_CSV_RE.match(etcsv)
    # Conditional GET yields 304
    rcsv2 = _get(
        client_admin,
        "admin",
        f"/api/report/export?year={year}&week={week}&format=csv",
        extra_headers={"If-None-Match": etcsv},
    )
    assert rcsv2.status_code == 304

    # XLSX export
    rx = _get(client_admin, "admin", f"/api/report/export?year={year}&week={week}&format=xlsx")
    assert rx.status_code == 200
    assert (
        rx.headers.get("Content-Type")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    etx = rx.headers.get("ETag")
    assert etx and ETAG_SITE_XLSX_RE.match(etx)
    assert len(rx.data) > 0

    # Mutate weekview -> ETag changes
    etag2 = _get(client_admin, "admin", wv_base).headers.get("ETag")
    _patch(
        client_admin,
        "admin",
        "/api/weekview/residents",
        json={
            "department_id": dep,
            "year": year,
            "week": week,
            "items": [
                {"day_of_week": 2, "meal": "lunch", "count": 5},
            ],
        },
        extra_headers={"If-Match": etag2},
    )
    rcsv3 = _get(client_admin, "admin", f"/api/report/export?year={year}&week={week}&format=csv")
    assert rcsv3.status_code == 200
    assert rcsv3.headers.get("ETag") != etcsv


@pytest.mark.usefixtures("enable_report", "enable_weekview")
def test_department_filter_limits_rows_in_csv(client_admin):
    dep = str(uuid.uuid4())
    year, week = 2025, 46
    wv_base = f"/api/weekview?year={year}&week={week}&department_id={dep}"
    etag0 = _get(client_admin, "admin", wv_base).headers.get("ETag")
    _patch(
        client_admin,
        "admin",
        "/api/weekview/residents",
        json={
            "department_id": dep,
            "year": year,
            "week": week,
            "items": [
                {"day_of_week": 1, "meal": "lunch", "count": 3},
            ],
        },
        extra_headers={"If-Match": etag0},
    )

    r = _get(client_admin, "admin", f"/api/report/export?year={year}&week={week}&department_id={dep}&format=csv")
    assert r.status_code == 200
    # Parse a bit and ensure departments section has only two rows (lunch+dinner) for the single department
    text = r.data.decode("utf-8")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # find header index for departments
    idx = lines.index("departments")
    header = lines[idx + 1]
    assert header.startswith("department_id,department_name,meal,normal,total,specials_json")
    # subsequent two lines should be for lunch and dinner of the same department
    dept_rows = lines[idx + 2 : idx + 4]
    assert len(dept_rows) == 2
    assert all(row.split(",")[0] == dep for row in dept_rows)
