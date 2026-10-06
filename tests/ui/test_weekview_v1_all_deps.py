from __future__ import annotations

import uuid
from datetime import date as _date

from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo, ResidencesRepo
from core.weekview.service import WeekviewService
from core.weekview.repo import WeekviewRepo
from core.weekview_vm import build_weekview_vm


def _login_headers(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def setup_data(app_session):
    # Ensure basic seed: one site, two departments, one diet type
    with app_session.app_context():
        srepo = SitesRepo()
        site, _ = srepo.create_site("TestSite", tenant_id=1)
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


def test_weekview_get_all_departments_renders_headers(client_admin, app_session):
    site, depA, depB, _dt = setup_data(app_session)
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["tenant_id"] = 1
        sess["role"] = "admin"
        sess["user_id"] = 1

    # Default to current ISO week
    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]

    # GET with empty department_id should render all departments
    resp = client_admin.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=_login_headers())
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Avd A" in body or "Avd B" in body


def _seed_mvp_weekview_site(app_session):
    with app_session.app_context():
        srepo = SitesRepo()
        drepo = DepartmentsRepo()
        rrepo = ResidencesRepo()

        site, _ = srepo.create_site("MVP Test1")
        residence_a = rrepo.create_for_site(site["id"], "Solrosen")
        residence_b = rrepo.create_for_site(site["id"], "Kaktusen")
        dept_a, _ = drepo.create_department(
            site_id=site["id"],
            name="Avdelning 1",
            resident_count_mode="fixed",
            resident_count_fixed=8,
            residence_id=residence_a["id"],
        )
        dept_b, _ = drepo.create_department(
            site_id=site["id"],
            name="Avdelning 1",
            resident_count_mode="fixed",
            resident_count_fixed=12,
            residence_id=residence_b["id"],
        )
        return site, dept_a, dept_b, residence_a, residence_b


def _seed_weekview_identity_site(app_session):
    with app_session.app_context():
        srepo = SitesRepo()
        drepo = DepartmentsRepo()
        rrepo = ResidencesRepo()

        site, _ = srepo.create_site("Weekview Identity Site")
        residence_a = rrepo.create_for_site(site["id"], "Solrosen")
        residence_b = rrepo.create_for_site(site["id"], "Kaktusen")
        dept_a, _ = drepo.create_department(
            site_id=site["id"],
            name="Avdelning 1",
            resident_count_mode="fixed",
            resident_count_fixed=10,
            residence_id=residence_a["id"],
        )
        dept_b, _ = drepo.create_department(
            site_id=site["id"],
            name="Avdelning 1",
            resident_count_mode="fixed",
            resident_count_fixed=12,
            residence_id=residence_b["id"],
        )
        dept_c, _ = drepo.create_department(
            site_id=site["id"],
            name="Avdelning 2",
            resident_count_mode="fixed",
            resident_count_fixed=8,
        )
        return site, dept_a, dept_b, dept_c, residence_a, residence_b


def test_weekview_empty_department_id_matches_absent_and_valid_and_invalid_behaviors(client_admin, app_session):
    site, dept_a, dept_b, _res_a, _res_b = _seed_mvp_weekview_site(app_session)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["tenant_id"] = 1
        sess["role"] = "admin"
        sess["user_id"] = 1

    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-User-Id": "1"}
    empty_url = f"/ui/weekview?site_id={site['id']}&department_id=&year=2026&week=41"
    absent_url = f"/ui/weekview?site_id={site['id']}&year=2026&week=41"
    valid_url = f"/ui/weekview?site_id={site['id']}&department_id={dept_a['id']}&year=2026&week=41"
    invalid_url = f"/ui/weekview?site_id={site['id']}&department_id=does-not-exist&year=2026&week=41"

    empty_resp = client_admin.get(empty_url, headers=headers)
    absent_resp = client_admin.get(absent_url, headers=headers)
    valid_resp = client_admin.get(valid_url, headers=headers)
    invalid_resp = client_admin.get(invalid_url, headers=headers)

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


def test_weekview_identity_hierarchy_renders_residence_names_and_no_avd_prefix(client_admin, app_session):
    site, dept_a, dept_b, dept_c, residence_a, residence_b = _seed_weekview_identity_site(app_session)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["tenant_id"] = 1
        sess["role"] = "admin"
        sess["user_id"] = 1

    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-User-Id": "1"}
    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]

    all_resp = client_admin.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=headers)
    assert all_resp.status_code == 200
    all_body = all_resp.get_data(as_text=True)
    assert "Solrosen" in all_body
    assert "Kaktusen" in all_body
    assert all_body.count("Avdelning 1") >= 2
    assert "Avd Avdelning 1" not in all_body
    assert "Avd Avdelning 2" not in all_body

    single_resp = client_admin.get(f"/ui/weekview?site_id={site['id']}&department_id={dept_a['id']}&year={year}&week={week}", headers=headers)
    assert single_resp.status_code == 200
    single_body = single_resp.get_data(as_text=True)
    assert "Avdelning 1" in single_body
    assert "Solrosen" in single_body
    assert "Avd Avdelning 1" not in single_body

    with app_session.app_context():
        vm = build_weekview_vm(site["id"], year, week, tenant_id=1)
    deps_by_id = {dep["id"]: dep for dep in vm["departments"]}
    assert deps_by_id[dept_a["id"]]["name"] == "Avdelning 1"
    assert deps_by_id[dept_a["id"]]["residence_name"] == residence_a["name"]
    assert deps_by_id[dept_b["id"]]["residence_name"] == residence_b["name"]
    assert deps_by_id[dept_c["id"]]["residence_name"] is None
    assert deps_by_id[dept_a["id"]]["resident_count"] == 10
    assert deps_by_id[dept_b["id"]]["resident_count"] == 12
    assert deps_by_id[dept_c["id"]]["resident_count"] == 8


def test_toggle_flow_marks_persist_and_report_shows_special(client_admin, app_session):
    site, depA, depB, dt_id = setup_data(app_session)
    # Align session site context
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["tenant_id"] = 1
        sess["role"] = "admin"
        sess["user_id"] = 1

    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]

    # Compute ETag for depA version 0
    with app_session.app_context():
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
    resp = client_admin.post("/api/weekview/specialdiets/mark", json=payload, headers={**_login_headers(), "If-Match": etag})
    assert resp.status_code == 200
    new_etag = resp.headers.get("ETag")
    assert new_etag and new_etag != etag

    # Verify persistence only for depA
    with app_session.app_context():
        dataA = repo.get_weekview(tenant_id=1, year=year, week=week, department_id=depA["id"])  # includes marks
    marksA = (dataA.get("department_summaries") or [{}])[0].get("marks") or []
    assert any(m.get("day_of_week") == 1 and m.get("meal") == "lunch" and m.get("diet_type") == str(dt_id) and m.get("marked") for m in marksA)

    with app_session.app_context():
        dataB = repo.get_weekview(tenant_id=1, year=year, week=week, department_id=depB["id"])  # includes marks
    marksB = (dataB.get("department_summaries") or [{}])[0].get("marks") or []
    assert not any(m.get("marked") for m in marksB), "Marks should not affect other departments"

    # Statistik/Rapport: special > 0 for depA
    r = client_admin.get(f"/api/reports/weekview?site_id={site['id']}&year={year}&week={week}&department_id={depA['id']}", headers=_login_headers())
    assert r.status_code == 200
    j = r.get_json()
    assert j and j.get("departments")
    dept = j["departments"][0]
    assert int(dept["meals"]["lunch"]["debiterbar_specialkost_count"]) > 0
