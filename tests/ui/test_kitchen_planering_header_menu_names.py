from datetime import date as _date

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site(site_id: str):
    from sqlalchemy import text
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS sites(
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              version INTEGER NOT NULL DEFAULT 0
            )
        """))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name, version) VALUES(:i, 'Plan Site', 0)"), {"i": site_id})
        db.commit()
    finally:
        db.close()


def _set_menu_variant(client, week: int, year: int, day: str, meal: str, variant: str, dish_name: str):
    payload = {
        "week": week,
        "year": year,
        "day": day,
        "meal": meal,
        "variant_type": variant,
        "dish_name": dish_name,
    }
    r = client.post("/menu/variant/set", json=payload, headers=HEADERS)
    assert r.status_code == 200


def test_header_shows_dish_names_for_lunch_and_dinner(app_session):
    client = app_session.test_client()
    site_id = "site-plan-1"
    _seed_site(site_id)
    today = _date.today()
    year = today.year
    week = today.isocalendar()[1]

    # Seed menu: Monday lunch Alt1/Alt2 and Dinner main (use Alt1)
    _set_menu_variant(client, week, year, day="Mon", meal="Lunch", variant="alt1", dish_name="Fiskgryta")
    _set_menu_variant(client, week, year, day="Mon", meal="Lunch", variant="alt2", dish_name="Veg Lasagne")
    _set_menu_variant(client, week, year, day="Mon", meal="Dinner", variant="alt1", dish_name="Pannkakor")

    # Lunch header shows Alt1/Alt2 names
    rv_lunch = client.get(f"/ui/kitchen/planering?site_id={site_id}&year={year}&week={week}&day=0&meal=lunch", headers=HEADERS)
    assert rv_lunch.status_code == 200
    html_l = rv_lunch.data.decode("utf-8")
    assert "Fiskgryta" in html_l
    assert "Veg Lasagne" in html_l

    # Dinner header shows dinner main name
    rv_din = client.get(f"/ui/kitchen/planering?site_id={site_id}&year={year}&week={week}&day=0&meal=dinner", headers=HEADERS)
    assert rv_din.status_code == 200
    html_d = rv_din.data.decode("utf-8")
    assert "Pannkakor" in html_d
