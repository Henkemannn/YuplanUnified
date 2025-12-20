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


def setup_data():
    # Ensure basic seed: one site, two departments, one diet type
    srepo = SitesRepo()
    site, _ = srepo.create_site("TestSite")
    drepo = DepartmentsRepo()
    depA, _ = drepo.create_department(site_id=site["id"], name="Avd A", resident_count_mode="fixed", resident_count_fixed=10)
    depB, _ = drepo.create_department(site_id=site["id"], name="Avd B", resident_count_mode="fixed", resident_count_fixed=12)
    trepo = DietTypesRepo()
    # Create a diet type (returns int ID)
    dt_id = trepo.create(tenant_id=1, name="Glutenfri", default_select=False)
    # Set defaults for both departments to 2
    drepo.upsert_department_diet_defaults(depA["id"], 0, [{"diet_type_id": str(dt_id), "default_count": 2}])
    drepo.upsert_department_diet_defaults(depB["id"], 0, [{"diet_type_id": str(dt_id), "default_count": 2}])
    return site, depA, depB, dt_id


def test_weekview_get_all_departments_renders_headers():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    site, depA, depB, _dt = setup_data()

    # Default to current ISO week
    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]

    # GET with empty department_id should render all departments
    resp = client.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=_login_headers())
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Avd A" in body or "Avd B" in body


def test_toggle_flow_marks_persist_and_report_shows_special():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    site, depA, depB, dt_id = setup_data()

    # Ensure active site context for strict validation
    with client.session_transaction() as s:
        s["site_id"] = site["id"]
        s["tenant_id"] = 1

    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]

    # Compute ETag for depA version 0
    svc = WeekviewService()
    repo = WeekviewRepo()
    # Ensure version row exists
    _ = repo.get_version(tenant_id=1, year=year, week=week, department_id=depA["id"])  # seeds 0
    etag = svc.build_etag(tenant_id=1, department_id=depA["id"], year=year, week=week, version=0)

    # Toggle Monday lunch mark for depA
    payload = {
        "year": year,
        "week": week,
        "department_id": depA["id"],
        "diet_type_id": str(dt_id),
        "meal": "Lunch",
        "weekday_abbr": "Mån",
        "marked": True,
    }
    resp = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**_login_headers(), "If-Match": etag})
    assert resp.status_code == 200
    new_etag = resp.headers.get("ETag")
    assert new_etag and new_etag != etag

    # Verify persistence only for depA
    dataA = repo.get_weekview(tenant_id=1, year=year, week=week, department_id=depA["id"])  # includes marks
    marksA = (dataA.get("department_summaries") or [{}])[0].get("marks") or []
    assert any(m.get("day_of_week") == 1 and m.get("meal") == "lunch" and m.get("diet_type") == str(dt_id) and m.get("marked") for m in marksA)

    dataB = repo.get_weekview(tenant_id=1, year=year, week=week, department_id=depB["id"])  # includes marks
    marksB = (dataB.get("department_summaries") or [{}])[0].get("marks") or []
    assert not any(m.get("marked") for m in marksB), "Marks should not affect other departments"

    # Statistik/Rapport: special > 0 for depA
    r = client.get(f"/api/reports/weekview?site_id={site['id']}&year={year}&week={week}&department_id={depA['id']}", headers=_login_headers())
    assert r.status_code == 200
    j = r.get_json()
    assert j and j.get("departments")
    dept = j["departments"][0]
    assert int(dept["meals"]["lunch"]["debiterbar_specialkost_count"]) > 0
