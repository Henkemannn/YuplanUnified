from datetime import date as _date
import uuid
from sqlalchemy import text

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
USER_HEADERS = {"X-User-Role": "user", "X-Tenant-Id": "1"}


def _seed_site_with_departments(app, dep_count=3):
    from core.db import create_all, get_session
    with app.app_context():
        create_all()
        db = get_session()
        try:
            site_id = str(uuid.uuid4())
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "PlanSite"})
            dep_ids = []
            for i in range(dep_count):
                dep_id = str(uuid.uuid4())
                dep_ids.append(dep_id)
                db.execute(
                    text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0)"),
                    {"i": dep_id, "s": site_id, "n": f"Avd {i+1}"},
                )
            db.commit()
            return site_id, dep_ids
        finally:
            db.close()


def _seed_menu_for_day(app, year, week, dep_ids):
    from core.models import Dish
    menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
    from core.db import get_new_session
    db = get_new_session()
    try:
        d1 = Dish(tenant_id=1, name="Lunch Alt1")
        db.add(d1)
        db.commit()
        db.refresh(d1)
        app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
    finally:
        db.close()


def test_get_planera_day_overview(client_admin):
    app = client_admin.application
    site_id, dep_ids = _seed_site_with_departments(app, dep_count=3)
    today = _date.today(); year, week, _ = today.isocalendar()
    _seed_menu_for_day(app, year, week, dep_ids)

    r = client_admin.get(f"/ui/planera/day?ui=unified&site_id={site_id}&date={today.isoformat()}&meal=lunch", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Planering" in html
    # All departments listed
    assert html.count("Avdelning") >= 1
    for i in range(1, 4):
        assert f"Avd {i}" in html
    # Totals visible
    assert "Totalt normalkost" in html


def test_post_mark_done_and_reflect_in_get(client_admin):
    app = client_admin.application
    site_id, dep_ids = _seed_site_with_departments(app, dep_count=3)
    today = _date.today()
    # POST mark two departments as done
    payload = {
        "site_id": site_id,
        "date": today.isoformat(),
        "meal": "lunch",
        "department_ids": [dep_ids[0], dep_ids[1]],
    }
    r = client_admin.post("/ui/planera/day/mark_done", data=payload, headers=ADMIN_HEADERS, follow_redirects=True)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Expect two rows show Klar
    assert html.count("Klar") >= 2


def test_security_and_validation(client_admin):
    app = client_admin.application
    site_id, _ = _seed_site_with_departments(app, dep_count=1)
    # Invalid meal
    r1 = client_admin.get(f"/ui/planera/day?ui=unified&site_id={site_id}&date={_date.today().isoformat()}&meal=brunch", headers=ADMIN_HEADERS)
    assert r1.status_code == 400
    # Invalid date
    r2 = client_admin.get(f"/ui/planera/day?ui=unified&site_id={site_id}&date=2025-13-40&meal=lunch", headers=ADMIN_HEADERS)
    assert r2.status_code == 400
