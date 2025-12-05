import uuid
import pytest


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_h("admin"),
    )
    assert resp.status_code == 200


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_report_api_and_ui_skeleton(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 12

    import os
    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "TestSite"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_id, "s": site_id, "n": "Avd X"})
            db.commit()
        finally:
            db.close()

    # API single department
    r_api = client_admin.get(f"/api/reports/weekview?site_id={site_id}&year={year}&week={week}&department_id={dep_id}", headers=_h("admin"))
    assert r_api.status_code == 200
    data = r_api.get_json()
    for key in ("site_id", "site_name", "year", "week", "meal_labels", "departments"):
        assert key in data
    assert data["site_id"] == site_id
    assert isinstance(data["departments"], list) and len(data["departments"]) == 1
    dept = data["departments"][0]
    assert dept["department_id"] == dep_id
    assert "meals" in dept and "lunch" in dept["meals"] and "dinner" in dept["meals"]
    lunch = dept["meals"]["lunch"]
    assert set(lunch.keys()) == {"residents_total", "debiterbar_specialkost_count", "normal_diet_count"}

    # API all departments
    r_api_all = client_admin.get(f"/api/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r_api_all.status_code == 200
    data_all = r_api_all.get_json()
    assert len(data_all["departments"]) >= 1

    # UI route
    r_ui = client_admin.get(f"/ui/reports/weekview?site_id={site_id}&year={year}&week={week}&department_id={dep_id}", headers=_h("admin"))
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    assert "Statistik – vecka" in html
