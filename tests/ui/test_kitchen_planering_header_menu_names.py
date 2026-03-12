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
    hdrs = dict(HEADERS)
    hdrs["X-Site-Id"] = "site-plan-1"
    r = client.post("/menu/variant/set", json=payload, headers=hdrs)
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
    _set_menu_variant(client, week, year, day="Mon", meal="Lunch", variant="dessert", dish_name="Äppelpaj")
    _set_menu_variant(client, week, year, day="Tue", meal="Lunch", variant="dessert", dish_name="Chokladmousse")
    _set_menu_variant(client, week, year, day="Mon", meal="Dinner", variant="alt1", dish_name="Pannkakor")

    # Lunch header shows Alt1/Alt2 names
    rv_lunch = client.get(f"/ui/kitchen/planering?site_id={site_id}&year={year}&week={week}&day=0&meal=lunch", headers=HEADERS)
    assert rv_lunch.status_code == 200
    html_l = rv_lunch.data.decode("utf-8")
    assert "Header" not in html_l
    assert "Fiskgryta" in html_l
    assert "Veg Lasagne" in html_l

    # Dinner header shows dinner main name
    rv_din = client.get(f"/ui/kitchen/planering?site_id={site_id}&year={year}&week={week}&day=0&meal=dinner", headers=HEADERS)
    assert rv_din.status_code == 200
    html_d = rv_din.data.decode("utf-8")
    assert "Pannkakor" in html_d

    # Dinner in normal mode still resolves dish label, but without redundant "Rätt:" line.
    rv_din_normal = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day=0&meal=dinner",
        headers=HEADERS,
    )
    assert rv_din_normal.status_code == 200
    html_dn = rv_din_normal.data.decode("utf-8")
    assert "Rätt:" not in html_dn
    assert 'id="kp-planering-title"' in html_dn
    assert "Pannkakor" in html_dn

    # Dessert in normal mode should use resolved dessert dish label
    rv_des_normal = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day=0&meal=dessert",
        headers=HEADERS,
    )
    assert rv_des_normal.status_code == 200
    html_ds = rv_des_normal.data.decode("utf-8")
    assert "Rätt:" not in html_ds
    assert 'id="kp-planering-title"' in html_ds
    assert "Äppelpaj" in html_ds

    # Tuesday dessert should not reuse Monday dessert
    rv_des_tue = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day=1&meal=dessert",
        headers=HEADERS,
    )
    assert rv_des_tue.status_code == 200
    html_tue = rv_des_tue.data.decode("utf-8")
    assert 'id="kp-planering-title"' in html_tue
    assert "Chokladmousse" in html_tue
