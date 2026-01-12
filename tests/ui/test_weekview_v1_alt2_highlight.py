from __future__ import annotations

import os
from datetime import date as _date

from flask.testing import FlaskClient

from core import create_app
from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
from core.weekview.repo import WeekviewRepo


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def _year_week():
    iso = _date.today().isocalendar()
    return iso[0], iso[1]


def seed_basic_with_diet():
    srepo = SitesRepo()
    site, _ = srepo.create_site("SiteOne")
    drepo = DepartmentsRepo()
    dep, _ = drepo.create_department(site_id=site["id"], name="Dept A", resident_count_mode="fixed", resident_count_fixed=10)
    # Create one diet type so diet rows render alongside Boende
    trepo = DietTypesRepo()
    dt = trepo.create(tenant_id=1, name="Glutenfri", default_select=False)
    drepo.upsert_department_diet_defaults(dep["id"], 0, [{"diet_type_id": str(dt), "default_count": 2}])
    return site, dep


def test_alt2_lunch_highlight_class_present_on_lunch_cells():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()

    site, dep = seed_basic_with_diet()
    year, week = _year_week()

    # Set alt2 flag for Wednesday (3)
    repo = WeekviewRepo()
    repo.set_alt2_flags(tenant_id=1, year=year, week=week, department_id=dep["id"], days=[3])

    resp = client.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=_h())
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Lunch cells should include ua-alt2 at least once
    assert "ua-alt2" in html
    # Dinner cells unchanged (we still have kvall class; we do not enforce absence of ua-alt2 on kvall explicitly here)
