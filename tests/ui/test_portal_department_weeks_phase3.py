from datetime import date as _date
import uuid
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    conn = get_session()
    try:
        site_id = "00000000-0000-0000-0000-00000000A000"
        dep_id = "00000000-0000-0000-0000-00000000A001"
        site = conn.execute(text("SELECT id FROM sites WHERE id=:id"), {"id": site_id}).fetchone()
        if not site:
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:id, 'Test Site A')"), {"id": site_id})
        dep = conn.execute(text("SELECT id FROM departments WHERE id=:id"), {"id": dep_id}).fetchone()
        if not dep:
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES (:id, :sid, 'Avd A', 'fixed', 5)"), {"id": dep_id, "sid": site_id})
        conn.commit()
        return site_id, dep_id
    finally:
        conn.close()


def test_portal_weeks_overview_grid_and_links(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_and_department()

    # Legacy path
    r1 = client.get(f"/portal/weeks?site_id={site_id}&department_id={dep_id}", headers=HEADERS)
    assert r1.status_code == 200
    html1 = r1.data.decode("utf-8")
    assert "Vecköversikt" in html1
    # Should render 12 week cards (anchors carry data-week attribute)
    assert html1.count('data-week="') == 12
    # Links should point to legacy weekly path
    assert "/portal/week?" in html1
    # Expect at least some future weeks marker text
    assert ("Kommer" in html1) or ("Ej påbörjad" in html1)
    # Current week highlight present
    assert "week-card--current" in html1

    # Enhetsportal path
    r2 = client.get(f"/ui/portal/weeks?site_id={site_id}&department_id={dep_id}", headers=HEADERS)
    assert r2.status_code == 200
    html2 = r2.data.decode("utf-8")
    assert html2.count('data-week="') == 12
    assert "/ui/portal/week?" in html2
    assert "week-card--current" in html2


def test_week_page_has_link_to_weeks_overview(app_session):
    from core.menu_service import MenuServiceDB
    from core.db import get_new_session
    from core.models import Dish

    client = app_session.test_client()
    site_id, dep_id = _seed_site_and_department()

    # Ensure a menu exists for current week so the page renders with content
    today = _date.today()
    year, week, _ = today.isocalendar()
    svc = MenuServiceDB()
    menu = svc.create_or_get_menu(1, week, year)

    # Create a dish and set alt1 for Monday
    db = get_new_session()
    try:
        d = Dish(tenant_id=1, name="Test Lunch")
        db.add(d)
        db.commit()
        db.refresh(d)
        svc.set_variant(1, menu.id, "mon", "lunch", "alt1", d.id)
    finally:
        db.close()

    # Legacy weekly path should include link to weeks overview
    r1 = client.get(f"/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}", headers=HEADERS)
    assert r1.status_code == 200
    html1 = r1.data.decode("utf-8")
    assert f"/portal/weeks?site_id={site_id}&department_id={dep_id}" in html1

    # Enhetsportal weekly path should include link to enhetsportal weeks overview
    r2 = client.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}", headers=HEADERS)
    assert r2.status_code == 200
    html2 = r2.data.decode("utf-8")
    assert f"/ui/portal/weeks?site_id={site_id}&department_id={dep_id}" in html2
