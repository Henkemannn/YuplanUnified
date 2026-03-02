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
            items = [
                "Bestall mer timbalbas",
                "Extra mjolk",
                "Kaffe",
                "Flingor",
                "Smor",
                "Tomater",
            ]
            from core.remember_to_order_repo import RememberToOrderRepo
            repo = RememberToOrderRepo()
            for item in items:
                repo.add(site_id, remember_week_key, item, None, "cook")
            db.commit()
        finally:
            db.close()

    with client_cook.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_cook.get("/ui/kitchen", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "data-testid=\"remember-to-order-card\"" in html
    assert "Kom ihåg att beställa" in html
    assert "data-testid=\"remember-to-order-add-form\"" in html
    assert "Bockade rader visas i 2 dagar och rensas sedan automatiskt." in html
    for item in [
        "Bestall mer timbalbas",
        "Extra mjolk",
        "Kaffe",
        "Flingor",
        "Smor",
        "Tomater",
    ]:
        assert item in html
    assert "Spara" not in html
