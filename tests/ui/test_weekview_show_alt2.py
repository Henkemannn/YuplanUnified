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
def test_weekview_shows_alt2_lunch_highlight(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    iso = _date.today().isocalendar()
    year, week = int(iso[0]), int(iso[1])

    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.admin_repo import SitesRepo, DepartmentsRepo

    with app.app_context():
        create_all()
        # Use repos to ensure proper tenant/site linkage
        srepo = SitesRepo()
        site, _ = srepo.create_site("Alt2 Demo Site")
        dep_repo = DepartmentsRepo()
        dep, _ = dep_repo.create_department(site_id=site["id"], name="Avd Alt2", resident_count_mode="fixed", resident_count_fixed=10)
        site_id = site["id"]
        dep_id = dep["id"]

    # Directly seed Alt2 flag (canonical schema: site_id, enabled)
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

    # Render weekview UI and assert lunch cell shows Alt2 highlight class
    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)

    # The lunch cell should include the is-alt2 class
    assert "meal-section--lunch is-alt2" in html
