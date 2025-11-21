import uuid
import pytest


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_week_api_and_ui_skeleton(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    year, week = 2025, 48

    from core.db import create_all, get_session
    from sqlalchemy import text
    import os
    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "PlaneraSite"})
            db.commit()
        finally:
            db.close()

    # Enable feature flag
    with app.app_context():
        reg = getattr(app, "feature_registry", None)
        if reg and not reg.has("ff.planera.enabled"):
            reg.add("ff.planera.enabled")
    # API
    r_api = client_admin.get(f"/api/planera/week?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r_api.status_code == 200
    data = r_api.get_json()
    for key in ("site_id", "site_name", "year", "week", "meal_labels", "days", "weekly_totals"):
        assert key in data
    assert isinstance(data["days"], list) and len(data["days"]) == 7
    assert set(data["weekly_totals"].keys()) == {"lunch", "dinner"}
    first_day = data["days"][0]
    assert set(first_day["meals"].keys()) == {"lunch", "dinner"}

    # UI
    r_ui = client_admin.get(f"/ui/planera/week?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    assert "Planera – vecka" in html and "PlaneraSite" in html
