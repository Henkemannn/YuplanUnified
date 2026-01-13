"""Unified Portal: Planera Day Phase 1 tests - read-only meal/day details UI."""
from __future__ import annotations

from flask.testing import FlaskClient
from sqlalchemy import text


HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_simple_day(app_session):
    # Use direct DB since tests elsewhere create tables; here we just ensure a site/department exists
    from core.db import get_session
    conn = get_session()
    try:
        # Ensure at least one site and department
        site_row = conn.execute(text("SELECT id FROM sites LIMIT 1")).fetchone()
        if not site_row:
            conn.execute(text("INSERT INTO sites (id, name) VALUES ('00000000-0000-0000-0000-000000000000', 'Test Site')"))
        dept_row = conn.execute(text("SELECT id FROM departments LIMIT 1")).fetchone()
        if not dept_row:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'Avd Alpha', 'fixed', 0)"))
        conn.commit()
    finally:
        conn.close()


def test_planera_day_renders_unified_template(app_session):
    client: FlaskClient = app_session.test_client()
    _seed_simple_day(app_session)

    # Use a fixed date
    site_id = "00000000-0000-0000-0000-000000000000"
    dept_id = "00000000-0000-0000-0000-000000000001"
    date_str = "2025-12-02"

    resp = client.get(
        f"/ui/planera/day?site_id={site_id}&department_id={dept_id}&date={date_str}&ui=unified",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # Title
    assert "M\u00e5ltidsvy" in html
    # Date and site
    assert date_str in html
    assert "Test Site" in html
    # Department name label
    assert "Avd Alpha" in html
    # At least one menu text or empty state
    assert ("Ingen meny" in html) or ("Alt 1" in html or "Alt 2" in html or "Dessert" in html)
