from __future__ import annotations

import os
import uuid
from datetime import date as _date

import pytest


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


@pytest.fixture
def disable_strict_csrf():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"


@pytest.mark.usefixtures("disable_strict_csrf")
def test_site_level_weekview_shows_alt2_on_lunch_cell(client_admin):
    """Render /ui/weekview with empty department_id and assert Alt2 class on lunch cell.

    Seeds canonical alt2 flag for one department/day, then verifies the site-level
    weekview template includes `is-alt2` on the lunch cell for that day.
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    iso = _date.today().isocalendar()
    year, week = int(iso[0]), int(iso[1])

    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo

    with app.app_context():
        create_all()
        # Create site and a department with fixed resident counts
        srepo = SitesRepo()
        site, _ = srepo.create_site("Alt2 Site-Level Demo")
        dep_repo = DepartmentsRepo()
        dep, _ = dep_repo.create_department(site_id=site["id"], name="Avd Alt2", resident_count_mode="fixed", resident_count_fixed=10)
        # Ensure at least one diet row renders by creating a diet type and setting defaults
        trepo = DietTypesRepo()
        dt_id = trepo.create(tenant_id=1, name="Glutenfri", default_select=False)
        dep_repo.upsert_department_diet_defaults(dep["id"], 0, [{"diet_type_id": str(dt_id), "default_count": 2}])
        site_id = site["id"]
        dep_id = dep["id"]

    # Seed Alt2 flag for Tuesday (day_of_week = 2)
    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO weekview_alt2_flags (site_id, department_id, year, week, day_of_week, enabled) "
                    "VALUES (:s,:d,:y,:w,:dow,1)"
                ),
                {"s": site_id, "d": dep_id, "y": year, "w": week, "dow": 2},
            )
            db.commit()
        finally:
            db.close()

    # Render site-level overview (no department_id) and assert lunch cell contains is-alt2
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id=&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Expect multiple lunch cells highlighted (Boende + at least one diet row)
    count = html.count("td class=\"is-alt2\"") + html.count(" class=\"is-alt2\"")
    assert count >= 2
