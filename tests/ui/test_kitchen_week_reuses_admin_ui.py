from datetime import date as _date

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basic_site_and_menu():
    from core.db import get_session
    from sqlalchemy import text
    conn = get_session()
    try:
        site_id = "00000000-0000-0000-0000-000000000040"
        dep_id = "00000000-0000-0000-0000-000000000041"
        if not conn.execute(text("SELECT 1 FROM sites WHERE id=:sid"), {"sid": site_id}).fetchone():
            conn.execute(text("INSERT INTO sites (id, name) VALUES (:sid, :name)"), {"sid": site_id, "name": "Kitchen Admin UI Site"})
        if not conn.execute(text("SELECT 1 FROM departments WHERE id=:did"), {"did": dep_id}).fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES (:did, :sid, :name, 'fixed', 7)"), {"did": dep_id, "sid": site_id, "name": "Avd UI"})
        conn.commit()
    finally:
        conn.close()
    # Add one diet type and defaults link so diet rows exist
    from core.admin_repo import DietTypesRepo
    dt_id = DietTypesRepo().create(site_id=site_id, name="Gluten", default_select=False)
    conn = get_session()
    try:
        from sqlalchemy import text
        conn.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
        conn.execute(text("INSERT OR IGNORE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES (:d, :t, 0)"), {"d": dep_id, "t": str(dt_id)})
        conn.commit()
    finally:
        conn.close()
    # Seed basic menu so menu icon appears
    from core.menu_service import MenuServiceDB
    from core.db import get_new_session
    from core.models import Dish
    svc = MenuServiceDB()
    today = _date.today()
    iso = today.isocalendar()
    year = iso[0]; week = iso[1]
    menu = svc.create_or_get_menu(1, week, year)
    db = get_new_session()
    try:
        d1 = Dish(tenant_id=1, name="Alt1 Test", category=None)
        d2 = Dish(tenant_id=1, name="Alt2 Test", category=None)
        db.add_all([d1, d2]); db.commit(); db.refresh(d1); db.refresh(d2)
        svc.set_variant(1, menu.id, "mon", "lunch", "alt1", d1.id)
        svc.set_variant(1, menu.id, "mon", "lunch", "alt2", d2.id)
        svc.publish_menu(1, menu.id)
    finally:
        db.close()
    return site_id, dep_id, year, week


def test_kitchen_week_renders_admin_ui_with_clickables(app_session):
    client = app_session.test_client()
    site_id, dep_id, year, week = _seed_basic_site_and_menu()
    rv = client.get(f"/ui/kitchen/week?site_id={site_id}&year={year}&week={week}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Admin-weekview markers
    assert "Boende" in html
    assert "Lunch" in html and "Kväll" in html
    # Kitchen mode click targets and JS
    assert "kostcell-btn" in html
    assert "/static/js/kitchen_week.js" in html
