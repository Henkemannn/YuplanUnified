import uuid
from datetime import date

import pytest


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_day_api_and_ui_skeleton(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    d = date(2025, 11, 20).isoformat()

    from core.admin_repo import DepartmentsRepo, SitesRepo
    from core.db import create_all

    with app.app_context():
        create_all()
        site, _ = SitesRepo().create_site(name="PlaneraSite", tenant_id=1)
        site_id = site["id"]
        department, _ = DepartmentsRepo().create_department(
            site_id=site_id,
            name="Avd P",
            resident_count_mode="fixed",
            resident_count_fixed=0,
        )
        dep_id = department["id"]

    # Ensure feature flag enabled (add or set True)
    with app.app_context():
        reg = getattr(app, "feature_registry", None)
        if reg:
            if not reg.has("ff.planera.enabled"):
                reg.add("ff.planera.enabled")
            reg.set("ff.planera.enabled", True)
    # API
    r_api = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))
    assert r_api.status_code == 200
    data = r_api.get_json()
    for key in ("site_id", "site_name", "date", "meal_labels", "departments", "totals"):
        assert key in data
    assert isinstance(data["departments"], list) and len(data["departments"]) == 1
    dept = data["departments"][0]
    assert dept["department_id"] == dep_id
    assert set(dept["meals"].keys()) == {"lunch", "dinner"}
    assert set(data["totals"].keys()) == {"lunch", "dinner"}

    # UI
    r_ui = client_admin.get(f"/ui/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    assert "Planera – dag" in html and "Avd P" in html
