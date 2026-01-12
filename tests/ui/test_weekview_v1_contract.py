from __future__ import annotations

import os
from datetime import date as _date

from flask.testing import FlaskClient

from core import create_app
from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
from core.weekview.service import WeekviewService
from core.weekview.repo import WeekviewRepo


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def seed_basic():
    srepo = SitesRepo()
    site, _ = srepo.create_site("SiteOne")
    drepo = DepartmentsRepo()
    depA, _ = drepo.create_department(site_id=site["id"], name="Dept A", resident_count_mode="fixed", resident_count_fixed=10)
    depB, _ = drepo.create_department(site_id=site["id"], name="Dept B", resident_count_mode="fixed", resident_count_fixed=12)
    return site, depA, depB


def seed_diets(site_id: str, dep_ids: list[str]):
    trepo = DietTypesRepo()
    gluten_id = trepo.create(tenant_id=1, name="Glutenfri", default_select=False)
    laktos_id = trepo.create(tenant_id=1, name="Laktosfri", default_select=False)
    drepo = DepartmentsRepo()
    # Defaults: Glutenfri=2; Laktosfri not set (absent)
    for dep_id in dep_ids:
        drepo.upsert_department_diet_defaults(dep_id, 0, [{"diet_type_id": str(gluten_id), "default_count": 2}])
    return gluten_id, laktos_id


def _year_week():
    iso = _date.today().isocalendar()
    return iso[0], iso[1]


def test_weekview_renders_all_departments_grid_and_boende_row():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    site, depA, depB = seed_basic()
    gluten_id, _ = seed_diets(site["id"], [depA["id"], depB["id"]])
    year, week = _year_week()

    resp = client.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=_h())
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Boende" in html
    assert "Dept A" in html or "Dept B" in html


def test_diet_rows_render_for_defaults_gt_zero_and_cells_have_data_attrs():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    site, depA, depB = seed_basic()
    gluten_id, _ = seed_diets(site["id"], [depA["id"], depB["id"]])
    year, week = _year_week()

    resp = client.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=_h())
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Section carries data-etag for each department
    assert 'data-etag="' in html
    # Diet cells have required attributes
    assert 'class="diet-cell' in html
    assert 'data-weekday="' in html
    assert 'data-meal="' in html
    assert 'data-diet-id="' in html


def test_site_lock_suppresses_site_switch_links():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    site, depA, depB = seed_basic()
    gluten_id, _ = seed_diets(site["id"], [depA["id"], depB["id"]])
    year, week = _year_week()

    # Set session site and lock
    with client.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["site_lock"] = True
        sess["role"] = "admin"
        sess["tenant_id"] = 1
    resp = client.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=_h())
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # No "Byt site" links when locked
    assert "Byt site:" not in html


def test_union_rule_renders_marked_diet_even_without_defaults():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    site, depA, depB = seed_basic()
    gluten_id, laktos_id = seed_diets(site["id"], [depA["id"], depB["id"]])
    year, week = _year_week()

    # Seed ETag for depA
    repo = WeekviewRepo()
    svc = WeekviewService()
    _ = repo.get_version(tenant_id=1, year=year, week=week, department_id=depA["id"])  # seed 0
    etag = svc.build_etag(tenant_id=1, department_id=depA["id"], year=year, week=week, version=0)

    # Mark Wed dinner for Laktosfri (not in defaults)
    payload = {
        "year": year,
        "week": week,
        "department_id": depA["id"],
        "diet_type_id": str(laktos_id),
        "meal": "Dinner",
        "weekday_abbr": "Ons",
        "marked": True,
    }
    r = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**_h(), "If-Match": etag})
    assert r.status_code == 200

    # Render weekview all and assert row for Laktosfri appears
    resp = client.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=_h())
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Expect a diet row containing data-diet-id of laktos_id at least once
    assert f'data-diet-id="{laktos_id}"' in html
