from datetime import date as _date
from sqlalchemy import text


def test_kitchen_dashboard_shows_remember_to_order_card(client_cook):
    app = client_cook.application
    site_id = "site-kitchen"
    from core.week_key import week_key_from_date
    remember_week_key = week_key_from_date(_date.today())

    with app.app_context():
        from core.db import get_session
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id, name, version) VALUES(:id, :name, 0)"), {"id": site_id, "name": "Kok Site"})
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS remember_to_order_items("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "site_id TEXT NOT NULL,"
                    "week_key TEXT NOT NULL,"
                    "text TEXT NOT NULL,"
                    "created_at TEXT NOT NULL,"
                    "created_by_role TEXT NOT NULL,"
                    "checked_at TEXT"
                    ")"
                )
            )
            db.execute(
                text(
                    "INSERT INTO remember_to_order_items(site_id, week_key, text, created_at, created_by_role, checked_at) "
                    "VALUES(:sid, :wk, 'Bestall mer timbalbas', '2026-01-01T00:00:00Z', 'cook', NULL)"
                ),
                {"sid": site_id, "wk": remember_week_key},
            )
            db.commit()
        finally:
            db.close()

    resp = client_cook.get(f"/ui/kitchen?site_id={site_id}", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "data-testid=\"remember-to-order-card\"" in html
    assert "Kom ihåg att beställa" in html
    assert "data-testid=\"remember-to-order-add-form\"" in html
    assert "Bockade rader visas i 2 dagar och rensas sedan automatiskt." in html
    assert "Spara" not in html
