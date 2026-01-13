import uuid
from datetime import date as _date
from sqlalchemy import text

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _seed_menu(app, year, week):
    from core.db import create_all, get_session
    from core.models import Dish
    with app.app_context():
        create_all()
        db = get_session()
        try:
            sid = str(uuid.uuid4()); did = str(uuid.uuid4())
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": sid, "n": "Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0)"), {"i": did, "s": sid, "n": "Avd"})
            db.commit()
            d1 = Dish(tenant_id=1, name="Köttbullar"); d2 = Dish(tenant_id=1, name="Fisk"); d3 = Dish(tenant_id=1, name="Glass")
            db.add_all([d1, d2, d3]); db.commit(); db.refresh(d1); db.refresh(d2); db.refresh(d3)
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt2", dish_id=d2.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="dessert", dish_id=d3.id)
            return sid, did
        finally:
            db.close()


def _enable_weekview(client_admin):
    r = client_admin.post("/features/set", json={"name": "ff.weekview.enabled", "enabled": True}, headers=ADMIN_HEADERS)
    assert r.status_code == 200


def test_navigation_data_attrs_present(client_admin):
    app = client_admin.application
    _enable_weekview(client_admin)
    year, week = 2025, 52
    sid, did = _seed_menu(app, year, week)
    # Use superuser to allow site override via querystring per hardened policy
    r = client_admin.get(f"/portal/week?site_id={sid}&department_id={did}&year={year}&week={week}", headers=_h("superuser"))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Container-level dataset
    assert f'data-site-id="{sid}"' in html
    assert f'data-department-id="{did}"' in html
    assert f'data-year="{year}"' in html
    assert f'data-week="{week}"' in html
    # Meal blocks have day + meal attributes for wiring
    assert 'data-day-key=' in html or 'data-day=' in html
    assert 'data-meal="lunch"' in html or 'data-meal=\"lunch\"' in html
    # A11y attributes remain intact
    assert 'role="button"' in html
    assert 'tabindex="0"' in html
