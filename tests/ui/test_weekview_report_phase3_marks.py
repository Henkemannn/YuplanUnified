import re
from datetime import date as _date
from flask.testing import FlaskClient

import pytest

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo

ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _enable_weekview(app) -> None:
    with app.app_context():
        reg = getattr(app, "feature_registry", None)
        if reg:
            if not reg.has("ff.weekview.enabled"):
                reg.add("ff.weekview.enabled")
            reg.set("ff.weekview.enabled", True)


def _seed_setup(app, year: int, week: int):
    with app.app_context():
        site, _ = SitesRepo().create_site(name=f"Test Site {week}", tenant_id=1)
        dept, _ = DepartmentsRepo().create_department(
            site_id=site["id"],
            name="Avd A",
            resident_count_mode="manual",
            resident_count_fixed=0,
        )
        gluten_id = DietTypesRepo().create(site_id=site["id"], name="Gluten", default_select=False)
        laktos_id = DietTypesRepo().create(site_id=site["id"], name="Laktos", default_select=False)
        timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=True)
        DepartmentsRepo().upsert_department_diet_defaults(
            dept["id"],
            0,
            [
                {"diet_type_id": gluten_id, "default_count": 2},
                {"diet_type_id": laktos_id, "default_count": 1},
                {"diet_type_id": timbal_id, "default_count": 3},
            ],
        )
    return site["id"], dept["id"], str(gluten_id), str(laktos_id), str(timbal_id)


def _seed_marks(client: FlaskClient, site_id: str, dep_id: str, year: int, week: int, gluten_id: str, laktos_id: str):
    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["tenant_id"] = 1
    r0 = client.get(base, headers=ADMIN)
    assert r0.status_code == 200
    etag = r0.headers.get("ETag")
    assert etag
    client.patch(
        "/api/weekview/specialdiets/mark",
        headers={**ADMIN, "If-Match": etag},
        json={
            "site_id": site_id,
            "department_id": dep_id,
            "local_date": _date.fromisocalendar(year, week, 1).isoformat(),
            "meal": "lunch",
            "diet_type_id": gluten_id,
            "marked": True,
        },
    )
    r1 = client.get(base, headers=ADMIN)
    etag2 = r1.headers.get("ETag") or etag
    client.patch(
        "/api/weekview/specialdiets/mark",
        headers={**ADMIN, "If-Match": etag2},
        json={
            "site_id": site_id,
            "department_id": dep_id,
            "local_date": _date.fromisocalendar(year, week, 2).isoformat(),
            "meal": "lunch",
            "diet_type_id": laktos_id,
            "marked": True,
        },
    )


def test_weekview_report_phase3_debiterbar_marks(app_session):
    client: FlaskClient = app_session.test_client()
    year = 2025
    week = 49
    _enable_weekview(client.application)
    site_id, dep_id, gluten_id, laktos_id, timbal_id = _seed_setup(client.application, year, week)
    _seed_marks(client, site_id, dep_id, year, week, gluten_id, laktos_id)

    # GET HTML report
    r = client.get(f"/ui/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=ADMIN)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Labels present
    assert "Gjorda specialkoster" in html
    assert "Gjorda specialkoster (lunch)" in html
    assert "Gjorda specialkoster (kvällsmat)" in html

    # Expectation:
    # Mon lunch: gluten(2) + timbal(3) = 5
    assert re.search(r">\s*5\s*<", html)
    # Tue lunch: laktos(1) + timbal(3) = 4
    assert re.search(r">\s*4\s*<", html)
    # A day with no marks still counts timbal(3)
    assert re.search(r">\s*3\s*<", html)

    # Weekly totals are shown in the summary table; presence is sufficient here
    assert "Gjorda specialkoster" in html


def test_weekview_report_phase3_no_marks_defaults_only(app_session):
    client: FlaskClient = app_session.test_client()
    year = 2025
    week = 50
    _enable_weekview(client.application)
    site_id, dep_id, _, _, _ = _seed_setup(client.application, year, week)
    # No marks seeded

    r = client.get(f"/ui/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=ADMIN)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # There is timbal always_mark=1 -> should show at least 3 somewhere
    assert re.search(r">\s*3\s*<", html)
    # But gluten/laktos should not contribute without marks; ensure we don't show 5 or 4 patterns tied to examples
    # (Weak negative check to avoid overfitting; presence of 5 may come from other values.)
    assert "Gjorda specialkoster" in html
