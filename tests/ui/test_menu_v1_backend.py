from __future__ import annotations

import os
from datetime import date as _date

from flask.testing import FlaskClient

from core import create_app
from core.admin_repo import SitesRepo
from core.menu_repo import MenuRepo


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def _year_week():
    iso = _date.today().isocalendar()
    return iso[0], iso[1]


def test_menu_day_and_week_storage_and_fetch():
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()

    srepo = SitesRepo()
    site, _ = srepo.create_site("SiteOne")
    year, week = _year_week()

    repo = MenuRepo()
    # Seed day 3 (Wed) lunch and dinner
    repo.upsert_menu_item(site_id=site["id"], year=year, week=week, day=3, meal="lunch", alt1_text="Kycklinggryta", alt2_text="Vegetarisk lasagne", dessert="Chokladpudding")
    repo.upsert_menu_item(site_id=site["id"], year=year, week=week, day=3, meal="dinner", alt1_text="Soppa", alt2_text=None, dessert=None)
    # Another day for week spread
    repo.upsert_menu_item(site_id=site["id"], year=year, week=week, day=1, meal="lunch", alt1_text="Fisk", alt2_text="Pasta", dessert=None)

    # Fetch day
    day3 = repo.get_menu_day(site["id"], year, week, 3)
    assert day3["lunch"]["alt1_text"] == "Kycklinggryta"
    assert day3["lunch"]["alt2_text"] == "Vegetarisk lasagne"
    assert day3["lunch"]["dessert"] == "Chokladpudding"
    assert day3["dinner"]["alt1_text"] == "Soppa"

    # Fetch week
    w = repo.get_menu_week(site["id"], year, week)
    assert "days" in w and "wed" in w["days"]
    assert w["days"]["wed"]["lunch"]["alt1"] == "Kycklinggryta"
    assert w["days"]["mon"]["lunch"]["alt1"] == "Fisk"

    # Endpoint: set session site_id and call /api/menu/day
    with client.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["role"] = "admin"
        sess["tenant_id"] = 1
    resp = client.get(f"/api/menu/day?year={year}&week={week}&day=3", headers=_h())
    assert resp.status_code == 200
    j = resp.get_json()
    assert j["lunch"]["alt2_text"] == "Vegetarisk lasagne"
    assert j["lunch"]["alt1_text"] == "Kycklinggryta"
    assert j["lunch"]["dessert"] == "Chokladpudding"
    # Dinner dessert key present with empty string default
    assert j["dinner"]["alt1_text"] == "Soppa"
    assert j["dinner"]["alt2_text"] == ""
    assert j["dinner"]["dessert"] == ""

    # Missing day returns stable keys with empty strings
    r2 = client.get(f"/api/menu/day?year={year}&week={week}&day=2", headers=_h())
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert set(j2.keys()) == {"lunch", "dinner"}
    for meal in ("lunch", "dinner"):
        assert set(j2[meal].keys()) == {"alt1_text", "alt2_text", "dessert"}
        assert j2[meal]["alt1_text"] == ""
        assert j2[meal]["alt2_text"] == ""
        assert j2[meal]["dessert"] == ""
