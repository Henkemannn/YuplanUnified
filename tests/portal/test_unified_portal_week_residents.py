import uuid
from datetime import date

import pytest


def _h(role="cook"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_portal_week_shows_residents_symbol_and_value(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 12

    from core.db import create_all, get_session
    from sqlalchemy import text
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "PortalSite"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',12,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_id, "s": site_id, "n": "Avd P"})
            db.commit()
        finally:
            db.close()
        # Seed variation: Monday lunch = 7 for selected week
        from core.residents_schedule_repo import ResidentsScheduleRepo
        ResidentsScheduleRepo().upsert_items(dep_id, week, [{"weekday": 1, "meal": "lunch", "count": 7}])

    # GET unified portal week view
    r = client_admin.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}", headers=_h("cook"))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Symbol present
    assert "👥" in html
    # Value present (7 appears for lunch)
    assert "7" in html
    # Ensure fixed fallback would differ (optional sanity)
    assert "12" in html
