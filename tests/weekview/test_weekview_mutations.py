import re
import uuid

import pytest

ETAG_RE = re.compile(r'^W/"weekview:dept:[0-9a-f-]+:year:\d{4}:week:\d{1,2}:v\d+"$')


def _get(client, role, path):
    return client.get(path, headers={"X-User-Role": role, "X-Tenant-Id": "1"})


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
def test_rbac_and_preconditions(client_admin):
    dep = str(uuid.uuid4())
    # viewer forbidden
    r = _patch(client_admin, "viewer", "/api/weekview", json={})
    assert r.status_code == 403

    # admin/editor must provide If-Match
    payload = {"department_id": dep, "year": 2025, "week": 45, "operations": []}
    r = _patch(client_admin, "admin", "/api/weekview", json=payload)
    assert r.status_code == 400
    assert r.get_json()["detail"] == "missing_if_match"


@pytest.mark.usefixtures("enable_weekview")
def test_happy_path_and_412(client_admin):
    dep = str(uuid.uuid4())
    site = str(uuid.uuid4())
    base = f"/api/weekview?year=2025&week=45&department_id={dep}"
    # Align session site context
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site

    # Initial GET -> v0
    r0 = _get(client_admin, "admin", base)
    assert r0.status_code == 200
    etag0 = r0.headers.get("ETag")
    assert etag0 and ETAG_RE.match(etag0)

    # PATCH with If-Match v0 -> v1
    ops = [{"day_of_week": 1, "meal": "lunch", "diet_type": "normal", "marked": True}]
    p = {"site_id": site, "department_id": dep, "year": 2025, "week": 45, "operations": ops}
    r1 = _patch(client_admin, "editor", "/api/weekview", json=p, extra_headers={"If-Match": etag0})
    assert r1.status_code == 200
    etag1 = r1.headers.get("ETag")
    assert etag1 and ETAG_RE.match(etag1)
    assert etag1 != etag0

    # GET now reflects v1 and marks include our toggle
    r2 = _get(client_admin, "admin", base)
    assert r2.status_code == 200
    assert r2.headers.get("ETag") == etag1
    data = r2.get_json()
    assert isinstance(data, dict)
    dep_summ = data.get("department_summaries")[0]
    marks = dep_summ.get("marks", [])
    assert any(m["day_of_week"] == 1 and m["meal"] == "lunch" and m["diet_type"] == "normal" and m["marked"] for m in marks)

    # 412 on stale If-Match
    r_stale = _patch(client_admin, "editor", "/api/weekview", json=p, extra_headers={"If-Match": etag0})
    assert r_stale.status_code == 412
    body = r_stale.get_json()
    assert body["detail"] == "etag_mismatch"


@pytest.mark.usefixtures("enable_weekview")
@pytest.mark.parametrize("meal", ["breakfast", "snack"])  # invalid meals
def test_validation_errors(client_admin, meal):
    dep = str(uuid.uuid4())
    site = str(uuid.uuid4())
    base = f"/api/weekview?year=2025&week=45&department_id={dep}"
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site
    r0 = _get(client_admin, "admin", base)
    etag0 = r0.headers.get("ETag")
    p = {
        "site_id": site,
        "department_id": dep,
        "year": 2025,
        "week": 45,
        "operations": [{"day_of_week": 0, "meal": meal, "diet_type": "normal", "marked": True}],
    }
    r = _patch(client_admin, "admin", "/api/weekview", json=p, extra_headers={"If-Match": etag0})
    assert r.status_code == 400


@pytest.mark.usefixtures("enable_weekview")
def test_batch_semantics_and_idempotence(client_admin):
    dep = str(uuid.uuid4())
    site = str(uuid.uuid4())
    base = f"/api/weekview?year=2025&week=45&department_id={dep}"
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site
    etag0 = _get(client_admin, "admin", base).headers.get("ETag")

    ops = [
        {"day_of_week": 1, "meal": "lunch", "diet_type": "normal", "marked": True},
        {"day_of_week": 2, "meal": "dinner", "diet_type": "veg", "marked": True},
    ]
    p = {"site_id": site, "department_id": dep, "year": 2025, "week": 45, "operations": ops}

    r1 = _patch(client_admin, "admin", "/api/weekview", json=p, extra_headers={"If-Match": etag0})
    assert r1.status_code == 200
    etag1 = r1.headers.get("ETag")

    # Immediate repeat with old ETag -> 412 (not silently idempotent)
    r2 = _patch(client_admin, "admin", "/api/weekview", json=p, extra_headers={"If-Match": etag0})
    assert r2.status_code == 412

    # New GET shows both marks
    data = _get(client_admin, "viewer", base).get_json()
    dep_summ = data.get("department_summaries")[0]
    marks = {(m["day_of_week"], m["meal"], m["diet_type"]) for m in dep_summ.get("marks", [])}
    assert (1, "lunch", "normal") in marks and (2, "dinner", "veg") in marks
