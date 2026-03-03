from datetime import date, datetime, timezone

from sqlalchemy import text


def _headers(role: str = "admin", tid: str = "1") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": tid}


def _day_key(value: date) -> str:
    from core.weekview.service import DAY_KEYS

    return DAY_KEYS[value.isoweekday() - 1]


def _seed_site(app, name: str) -> str:
    from core.admin_repo import SitesRepo

    with app.app_context():
        site, _ = SitesRepo().create_site(name)
    return site["id"]


def _insert_menu(app, *, site_id: str, status: str, dish_name: str | None = None) -> dict[str, int | str]:
    today = date.today()
    year, week = today.isocalendar()[0], today.isocalendar()[1]
    day_key = _day_key(today)

    with app.app_context():
        from core.db import get_session
        from core.menu_service import MenuServiceDB
        from core.models import Dish

        svc = MenuServiceDB()
        menu = svc.create_or_get_menu(1, site_id, week, year)
        menu_id = menu.id

        dish_id = None
        if dish_name:
            db = get_session()
            try:
                dish = Dish(tenant_id=1, name=dish_name, category=None)
                db.add(dish)
                db.commit()
                db.refresh(dish)
                dish_id = int(dish.id)
            finally:
                db.close()
        if dish_id and menu_id:
            svc.set_variant(1, menu_id, day_key, "lunch", "alt1", dish_id)

        if status == "published":
            svc.publish_menu(1, menu_id)

    return {"year": int(year), "week": int(week), "day_key": str(day_key)}


def test_admin_dashboard_today_menu_draft_state(client_admin):
    app = client_admin.application
    site_id = _seed_site(app, "Draft Today Site")
    _insert_menu(app, site_id=site_id, status="draft")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.get("/ui/admin", headers=_headers("admin"))
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    assert "Utkast finns" in html
    assert "Ingen meny" not in html


def test_admin_dashboard_today_menu_published_state(client_admin):
    app = client_admin.application
    site_id = _seed_site(app, "Published Today Site")
    info = _insert_menu(app, site_id=site_id, status="published", dish_name="Test Dish")

    with app.app_context():
        from core.menu_service import MenuServiceDB

        svc = MenuServiceDB()
        today = date.today()
        today_menu = svc.get_today_menu_for_site(1, site_id, today)
        assert today_menu.get("lunch_alt1") == "Test Dish", f"today_menu={today_menu}"

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.get("/ui/admin", headers=_headers("admin"))
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    debug_line = next((line.strip() for line in html.splitlines() if "DEBUG:" in line), "")

    assert "Dagens meny" in html
    assert "Test Dish" in html, f"DEBUG line: {debug_line}"
    assert "Utkast finns" not in html
