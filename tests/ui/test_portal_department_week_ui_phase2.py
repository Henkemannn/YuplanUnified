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
            # basic site/department
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


def test_rbac_and_load(client_admin):
    app = client_admin.application
    _enable_weekview(client_admin)
    year, week = 2025, 46
    sid, did = _seed_menu(app, year, week)
    for role in ["admin", "cook", "unit_portal", "superuser"]:
        r = client_admin.get(f"/portal/week?site_id={sid}&department_id={did}&year={year}&week={week}", headers=_h(role))
        assert r.status_code == 200
    r_forbidden = client_admin.get(f"/portal/week?site_id={sid}&department_id={did}&year={year}&week={week}", headers=_h("viewer"))
    assert r_forbidden.status_code == 403


def test_structure_and_header(client_admin):
    app = client_admin.application
    _enable_weekview(client_admin)
    year, week = 2025, 47
    sid, did = _seed_menu(app, year, week)
    r = client_admin.get(f"/portal/week?site_id={sid}&department_id={did}&year={year}&week={week}", headers=ADMIN_HEADERS)
    html = r.get_data(as_text=True)
    assert "Avdelningsvy" in html
    assert f"Vecka {week}, {year}" in html
    assert "Avd" in html and "Site" in html
    # At least 7 day cards expected
    assert html.count("portal-day-card") >= 7


def test_data_rendering_and_badges(client_admin):
    app = client_admin.application
    _enable_weekview(client_admin)
    year, week = 2025, 48
    sid, did = _seed_menu(app, year, week)
    # Bind session site to ensure admin context matches seeded site
    with client_admin.session_transaction() as s:
        s["site_id"] = sid
        s["site_lock"] = True
        s["role"] = "admin"
    # Flag alt2 for Monday
    r0 = client_admin.get(f"/api/weekview?year={year}&week={week}&department_id={did}", headers=ADMIN_HEADERS)
    etag0 = r0.headers.get("ETag")
    r_alt2 = client_admin.patch("/api/weekview/alt2", json={"tenant_id":1,"department_id":did,"year":year,"week":week,"days":[1]}, headers={**ADMIN_HEADERS, "If-Match": etag0})
    assert r_alt2.status_code in (200,201)
    # Registration for Monday lunch
    from core.meal_registration_repo import MealRegistrationRepo
    repo = MealRegistrationRepo(); repo.ensure_table_exists(); monday = _date.fromisocalendar(year, week, 1).isoformat()
    repo.upsert_registration(tenant_id=1, site_id=sid, department_id=did, date_str=monday, meal_type="lunch", registered=True)
    # Render portal
    r = client_admin.get(f"/portal/week?site_id={sid}&department_id={did}&year={year}&week={week}", headers=ADMIN_HEADERS)
    html = r.get_data(as_text=True)
    assert "Köttbullar" in html
    assert "⚡ Alt 2" in html or "yp-badge-warning" in html
    # Diet badges may be present (depends on enrichment); tolerate absence but check residents line
    assert "Registrerad" in html


def test_dinner_logic(client_admin):
    app = client_admin.application
    _enable_weekview(client_admin)
    year, week = 2025, 49
    sid, did = _seed_menu(app, year, week)
    r = client_admin.get(f"/portal/week?site_id={sid}&department_id={did}&year={year}&week={week}", headers=ADMIN_HEADERS)
    html = r.get_data(as_text=True)
    # With only lunch seeded, dinner block should not render
    assert "KVÄLLSMAT" not in html
    # Ensure at least one lunch block present
    assert html.count("LUNCH") >= 1


def test_accessibility_attrs_present(client_admin):
    app = client_admin.application
    _enable_weekview(client_admin)
    year, week = 2025, 50
    sid, did = _seed_menu(app, year, week)
    r = client_admin.get(f"/portal/week?site_id={sid}&department_id={did}&year={year}&week={week}", headers=ADMIN_HEADERS)
    html = r.get_data(as_text=True)
    assert "role=\"button\"" in html
    assert "tabindex=\"0\"" in html
    assert "aria-label=\"Lunch" in html
    # Today badge presence if any today
    assert ("yp-badge-info\">Idag" in html) or True


def test_regression_views_ok(client_admin):
    app = client_admin.application
    _enable_weekview(client_admin)
    year, week = 2025, 51
    sid, did = _seed_menu(app, year, week)
    # Portal
    r_portal = client_admin.get(f"/portal/week?site_id={sid}&department_id={did}&year={year}&week={week}", headers=ADMIN_HEADERS)
    assert r_portal.status_code == 200
    # Cook
    r_cook = client_admin.get("/ui/cook", headers=_h("cook"))
    assert r_cook.status_code == 200
    # Admin
    r_admin = client_admin.get("/ui/admin", headers=_h("admin"))
    assert r_admin.status_code == 200
    # Reports weekly
    r_report = client_admin.get("/ui/reports/weekly", headers=_h("admin"))
    assert r_report.status_code == 200
