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

    from core.db import create_all, get_session
    from sqlalchemy import text
    import os
    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "PlaneraSite"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_id, "s": site_id, "n": "Avd P"})
            db.commit()
        finally:
            db.close()

    # Enable feature flag
    with app.app_context():
        reg = getattr(app, "feature_registry", None)
        if reg and not reg.has("ff.planera.enabled"):
            reg.add("ff.planera.enabled")
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
