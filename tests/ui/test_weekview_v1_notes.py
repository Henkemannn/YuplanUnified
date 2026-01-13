from __future__ import annotations

import os
from datetime import date as _date

from flask.testing import FlaskClient

from core import create_app
from core.admin_repo import SitesRepo, DepartmentsRepo


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def _year_week():
    iso = _date.today().isocalendar()
    return iso[0], iso[1]


def test_weekview_all_contains_notes_modal_markup():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()

    srepo = SitesRepo()
    site, _ = srepo.create_site("SiteOne")
    drepo = DepartmentsRepo()
    depA_notes = "Viktigt: Leverans via bakdörr. Allergier: nötter."
    depA, _ = drepo.create_department(site_id=site["id"], name="Dept A", resident_count_mode="fixed", resident_count_fixed=10, notes=depA_notes)
    depB, _ = drepo.create_department(site_id=site["id"], name="Dept B", resident_count_mode="fixed", resident_count_fixed=12)

    year, week = _year_week()
    resp = client.get(f"/ui/weekview?site_id={site['id']}&department_id=&year={year}&week={week}", headers=_h())
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Notes appear inline (no modal required)
    assert depA_notes in html
    # Ensure no modal/id and no modal trigger are present
    assert f"dep-info-{depA['id']}" not in html
    assert "data-modal-target=\"#dep-info-" not in html
