from __future__ import annotations

import os
from datetime import date as _date

from flask.testing import FlaskClient

from core import create_app
from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
from core.weekview.service import WeekviewService
from core.weekview.repo import WeekviewRepo


def _login_headers(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def seed_basic():
    srepo = SitesRepo()
    site, _ = srepo.create_site("TestSite")
    drepo = DepartmentsRepo()
    dep, _ = drepo.create_department(site_id=site["id"], name="Avd A", resident_count_mode="fixed", resident_count_fixed=10)
    trepo = DietTypesRepo()
    dt_id = trepo.create(tenant_id=1, name="Glutenfri", default_select=False)
    drepo.upsert_department_diet_defaults(dep["id"], 0, [{"diet_type_id": str(dt_id), "default_count": 2}])
    return site, dep, dt_id


def test_etag_stale_then_retry_with_fresh_etag():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    site, dep, dt_id = seed_basic()

    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]

    svc = WeekviewService()
    repo = WeekviewRepo()
    _ = repo.get_version(tenant_id=1, year=year, week=week, department_id=dep["id"])  # seed version=0
    etag_v0 = svc.build_etag(tenant_id=1, department_id=dep["id"], year=year, week=week, version=0)

    payload = {
        "year": year,
        "week": week,
        "department_id": dep["id"],
        "diet_type_id": str(dt_id),
        "meal": "Lunch",
        "weekday_abbr": "Mån",
        "marked": True,
    }

    # First toggle: should 200 and bump version
    r1 = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**_login_headers(), "If-Match": etag_v0})
    assert r1.status_code == 200

    # Second toggle with stale ETag: expect 412
    r2 = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**_login_headers(), "If-Match": etag_v0})
    assert r2.status_code == 412

    # Fetch fresh ETag via new helper endpoint
    r3 = client.get(f"/api/weekview/etag?department_id={dep['id']}&year={year}&week={week}", headers=_login_headers())
    assert r3.status_code == 200
    etag_new = r3.get_json()["etag"]
    assert etag_new and etag_new != etag_v0

    # Retry with new ETag should succeed
    r4 = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**_login_headers(), "If-Match": etag_new})
    assert r4.status_code == 200
