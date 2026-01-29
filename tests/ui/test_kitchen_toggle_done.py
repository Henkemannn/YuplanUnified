from datetime import date as _date

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        from sqlalchemy import text
        site = conn.execute(text("SELECT id FROM sites WHERE id='00000000-0000-0000-0000-000000000000'"))
        if not site.fetchone():
            conn.execute(text("INSERT INTO sites (id, name) VALUES ('00000000-0000-0000-0000-000000000000', 'Test Site')"))
        dep = conn.execute(text("SELECT id FROM departments WHERE id='00000000-0000-0000-0000-000000000001'"))
        if not dep.fetchone():
            conn.execute(text("INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed) VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'Avd Alpha', 'fixed', 5)"))
        conn.commit()
    finally:
        conn.close()


def _ensure_menu_for_week(tenant_id: int, year: int, week: int) -> None:
    from core.menu_service import MenuServiceDB
    from core.db import get_new_session
    from core.models import Dish

    svc = MenuServiceDB()
    menu = svc.create_or_get_menu(tenant_id, week, year)
    db = get_new_session()
    try:
        d1 = Dish(tenant_id=tenant_id, name="Alt1 Renskav", category=None)
        d2 = Dish(tenant_id=tenant_id, name="Alt2 Falukorv", category=None)
        db.add_all([d1, d2])
        db.commit()
        db.refresh(d1); db.refresh(d2)
        dish_ids = [d1.id, d2.id]
    finally:
        db.close()
    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt1", dish_ids[0])
    svc.set_variant(tenant_id, menu.id, "mon", "lunch", "alt2", dish_ids[1])
    svc.publish_menu(tenant_id, menu.id)


def test_kitchen_week_toggle_done(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    department_id = "00000000-0000-0000-0000-000000000001"
    year = 2025
    week = 49
    tid = 1

    _ensure_menu_for_week(tid, year, week)
    # Create a real diet type and use its ID for toggle
    from core.admin_repo import DietTypesRepo
    dt_id = DietTypesRepo().create(site_id=site_id, name="Gluten", default_select=False)
    # GET should return 200
    rv = client.get(
        f"/ui/kitchen/week?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert rv.status_code == 200

    # Toggle done for Monday lunch, using a real diet type id
    payload = {
        "year": year,
        "week": week,
        "department_id": department_id,
        "day_index": 1,
        "meal": "lunch",
        "kosttyp_id": str(dt_id),
        "done": True,
    }
    r2 = client.post("/ui/kitchen/week/toggle_done", json=payload, headers=HEADERS)
    assert r2.status_code == 200
    data = r2.get_json()
    assert data.get("ok") is True
    assert data.get("done") is True

    # Refresh and ensure the grid renders (ring presence cannot be asserted server-side without JS), but route remains 200
    rv2 = client.get(
        f"/ui/kitchen/week?site_id={site_id}&department_id={department_id}&year={year}&week={week}",
        headers=HEADERS,
    )
    assert rv2.status_code == 200
