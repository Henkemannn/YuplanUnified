from datetime import date, datetime, timezone

from sqlalchemy import text


def _headers(role: str = "admin", tid: str = "1") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": tid}


def _day_key(value: date) -> str:
    return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][value.isoweekday() - 1]


def _seed_site(app, name: str) -> str:
    from core.admin_repo import SitesRepo

    with app.app_context():
        site, _ = SitesRepo().create_site(name)
    return site["id"]


def _insert_menu(app, *, site_id: str, status: str, dish_name: str | None = None) -> None:
    today = date.today()
    year, week = today.isocalendar()[0], today.isocalendar()[1]
    day_key = _day_key(today)

    with app.app_context():
        from core.db import get_session

        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO menus (tenant_id, site_id, week, year, status, updated_at) "
                    "VALUES (:tid, :sid, :week, :year, :status, :updated_at)"
                ),
                {
                    "tid": 1,
                    "sid": site_id,
                    "week": week,
                    "year": year,
                    "status": status,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            menu_row = db.execute(
                text(
                    "SELECT id FROM menus WHERE site_id=:sid AND week=:week AND year=:year "
                    "AND status=:status ORDER BY id DESC LIMIT 1"
                ),
                {"sid": site_id, "week": week, "year": year, "status": status},
            ).fetchone()
            menu_id = int(menu_row[0]) if menu_row else None

            if dish_name and menu_id:
                db.execute(
                    text("INSERT INTO dishes (tenant_id, name, category) VALUES (:tid, :name, :cat)"),
                    {"tid": 1, "name": dish_name, "cat": "main"},
                )
                dish_row = db.execute(
                    text("SELECT id FROM dishes WHERE name=:name ORDER BY id DESC LIMIT 1"),
                    {"name": dish_name},
                ).fetchone()
                dish_id = int(dish_row[0]) if dish_row else None
                if dish_id:
                    db.execute(
                        text(
                            "INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id) "
                            "VALUES (:menu_id, :day, :meal, :variant, :dish_id)"
                        ),
                        {
                            "menu_id": menu_id,
                            "day": day_key,
                            "meal": "lunch",
                            "variant": "standard",
                            "dish_id": dish_id,
                        },
                    )
            db.commit()
        finally:
            db.close()


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
    _insert_menu(app, site_id=site_id, status="published", dish_name="Test Dish")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.get("/ui/admin", headers=_headers("admin"))
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    assert "Dagens meny" in html
    assert "Test Dish" in html
    assert "Utkast finns" not in html
