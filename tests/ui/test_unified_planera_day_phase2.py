import re
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_simple_day():
    from core.db import get_session
    conn = get_session()
    try:
        site_row = conn.execute(text("SELECT id FROM sites WHERE id='00000000-0000-0000-0000-000000000000'")) .fetchone()
        if not site_row:
            conn.execute(text("INSERT INTO sites (id, name) VALUES ('00000000-0000-0000-0000-000000000000', 'Test Site')"))
        dept_row = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-000000000001'")) .fetchone()
        if not dept_row:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'Avd Alpha', 'fixed', 0)"))
        conn.commit()
    finally:
        conn.close()


def test_unified_planera_day_phase2_sections(app_session):
    client = app_session.test_client()
    _seed_simple_day()

    site_id = "00000000-0000-0000-0000-000000000000"
    dept_id = "00000000-0000-0000-0000-000000000001"
    date_str = "2025-12-02"

    resp = client.get(
        f"/ui/planera/day?site_id={site_id}&department_id={dept_id}&date={date_str}&ui=unified",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    for heading in ["Prepp", "Inköp", "Frys", "Recept"]:
        assert heading in html

    assert "Kommer senare" in html

    m = re.search(r'data-component-id=\"([^\"]+)\"', html)
    if m:
        assert m.group(1).strip() != ""
