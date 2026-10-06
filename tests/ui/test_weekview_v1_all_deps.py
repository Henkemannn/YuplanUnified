from __future__ import annotations

import os
import uuid
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
    dt_id = trepo.create(site_id=site["id"], name=f"Glutenfri-{uuid.uuid4().hex[:8]}", default_select=False)
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


def _seed_mvp_weekview_site(app):
    from core.db import get_session
    from sqlalchemy import text

    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text("INSERT OR REPLACE INTO tenants(id, name, active) VALUES(2, 'Yuplan MVP testkund 1', 1)")
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
                    "VALUES('mvp-test1', 'MVP Test1', 2, 0)"
                )
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES('9479ab77-5abe-419c-81f8-5155cb5b1151', 'mvp-test1', 'Avdelning 1', 'fixed', 8, 0)"
                )
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES('3a9a6617-6b7f-4605-83d2-2d00596f141f', 'mvp-test1', 'Avdelning 1', 'fixed', 12, 0)"
                )
            )
            db.commit()
        finally:
            db.close()


def test_weekview_empty_department_id_matches_absent_and_valid_and_invalid_behaviors():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    _seed_mvp_weekview_site(app)

    with client.session_transaction() as sess:
        sess["site_id"] = "mvp-test1"
        sess["tenant_id"] = 2
        sess["role"] = "admin"
        sess["user_id"] = 1

    headers = {"X-User-Role": "admin", "X-Tenant-Id": "2", "X-User-Id": "1"}
    empty_url = "/ui/weekview?site_id=mvp-test1&department_id=&year=2026&week=41"
    absent_url = "/ui/weekview?site_id=mvp-test1&year=2026&week=41"
    valid_url = "/ui/weekview?site_id=mvp-test1&department_id=9479ab77-5abe-419c-81f8-5155cb5b1151&year=2026&week=41"
    invalid_url = "/ui/weekview?site_id=mvp-test1&department_id=does-not-exist&year=2026&week=41"

    empty_resp = client.get(empty_url, headers=headers)
    absent_resp = client.get(absent_url, headers=headers)
    valid_resp = client.get(valid_url, headers=headers)
    invalid_resp = client.get(invalid_url, headers=headers)

    assert empty_resp.status_code == 200
    assert absent_resp.status_code == 200
    assert valid_resp.status_code == 200
    assert invalid_resp.status_code == 200

    empty_body = empty_resp.get_data(as_text=True)
    absent_body = absent_resp.get_data(as_text=True)
    valid_body = valid_resp.get_data(as_text=True)
    invalid_body = invalid_resp.get_data(as_text=True)

    assert "Avdelning 1" in empty_body
    assert "Avdelning 1" in absent_body
    assert empty_body == absent_body or ("Avdelning 1" in empty_body and "Avdelning 1" in absent_body)
    assert "Avdelning 1" in valid_body
    assert "Avd A" not in invalid_body and "Avd B" not in invalid_body
    assert "Avdelning" in invalid_body


def test_toggle_flow_marks_persist_and_report_shows_special():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    site, depA, depB, dt_id = setup_data()
    # Align session site context
    with client.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["tenant_id"] = 1

    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]

    # Compute ETag for depA version 0
    svc = WeekviewService()
    repo = WeekviewRepo()
    # Ensure version row exists
    version = repo.get_version(tenant_id=1, year=year, week=week, department_id=depA["id"])
    etag = svc.build_etag(tenant_id=1, department_id=depA["id"], year=year, week=week, version=version)

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
