"""ETag delta behavior tests for Department Portal endpoint.

Validates ADR decisions in `docs/adr/ADR_department_portal_composite_and_etags.md`:
- No change => 304 with identical portal ETag
- Menu text change => new portal ETag and updated payload
- Choice (selected_alt) change => new portal ETag

Focus: Read-only GET /portal/department/week
Scope: Does not introduce new production logic; only asserts existing behavior.
"""
from __future__ import annotations

from typing import Dict
from sqlalchemy import text
from core.db import get_session

YEAR = 2025
WEEK = 47
DEPT_ID = "99999999-1111-2222-3333-444444444444"
SITE_ID = "ssssssss-tttt-uuuu-vvvv-wwwwwwwwwwww"


def _h():  # minimal required headers for current auth approach (claims via environ_overrides)
    return {
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
    }


def _seed_base(db, alt2_enabled_monday: int = 1, dish_name_alt1: str = "Pannbiff"):
    """Seed minimal data needed for portal week composition."""
    # Departments + note
    db.execute(text(
        """
        CREATE TABLE IF NOT EXISTS departments(
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT,
            notes TEXT NULL,
            resident_count_mode TEXT NOT NULL DEFAULT 'manual'
        )
        """
    ))
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, notes, resident_count_mode) VALUES(:i,:s,'Test Avd','Note','manual')"), {"i": DEPT_ID, "s": SITE_ID})
    # Weekview core tables
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_registrations(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal,diet_type))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_residents_count(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, count INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_alt2_flags(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, is_alt2 INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS department_menu_choices(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, weekday INTEGER NOT NULL, meal TEXT NOT NULL DEFAULT 'lunch', selected_variant TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT, UNIQUE(tenant_id,site_id,department_id,year,week,weekday,meal))"))
    # Cleanup existing rows for idempotent seeding across tests
    db.execute(text("DELETE FROM weekview_registrations WHERE tenant_id='1' AND department_id=:d AND year=:y AND week=:w"), {"d": DEPT_ID, "y": YEAR, "w": WEEK})
    db.execute(text("DELETE FROM weekview_residents_count WHERE tenant_id='1' AND department_id=:d AND year=:y AND week=:w"), {"d": DEPT_ID, "y": YEAR, "w": WEEK})
    db.execute(text("DELETE FROM weekview_alt2_flags WHERE tenant_id='1' AND department_id=:d AND year=:y AND week=:w"), {"d": DEPT_ID, "y": YEAR, "w": WEEK})
    # Monday residents + diets
    db.execute(text("INSERT OR REPLACE INTO weekview_residents_count VALUES(1,:d,:y,:w,1,'lunch',10)"), {"d": DEPT_ID, "y": YEAR, "w": WEEK})
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations VALUES(1,:d,:y,:w,1,'lunch','Gluten',1)"), {"d": DEPT_ID, "y": YEAR, "w": WEEK})
    # Alt2 drift flag Monday (controls flags.alt2_lunch)
    db.execute(text("INSERT OR REPLACE INTO weekview_alt2_flags VALUES(1,:d,:y,:w,1,:is_alt2)"), {"d": DEPT_ID, "y": YEAR, "w": WEEK, "is_alt2": alt2_enabled_monday})
    # Menu choice flags table (used for selected_alt for now)
    db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"))
    db.execute(text("DELETE FROM alt2_flags WHERE department_id=:d AND week=:w"), {"d": DEPT_ID, "w": WEEK})
    db.execute(text("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,1,:enabled,1)"), {"s": SITE_ID, "d": DEPT_ID, "w": WEEK, "enabled": alt2_enabled_monday})
    # Menu tables
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
    # Remove prior menu data with same IDs (idempotent re-seed)
    db.execute(text("DELETE FROM menu_variants WHERE menu_id=601"))
    db.execute(text("DELETE FROM menus WHERE id=601"))
    db.execute(text("DELETE FROM dishes WHERE id IN (501,502,503,504)"))
    # Insert dishes (alt1 + alt2 + dessert + dinner)
    db.execute(text("INSERT INTO dishes(id,tenant_id,name,category) VALUES(501,1,:n,NULL)"), {"n": dish_name_alt1})
    db.execute(text("INSERT INTO dishes(id,tenant_id,name,category) VALUES(502,1,'Fiskgratäng',NULL)"))
    db.execute(text("INSERT INTO dishes(id,tenant_id,name,category) VALUES(503,1,'Fruktsallad',NULL)"))
    db.execute(text("INSERT INTO dishes(id,tenant_id,name,category) VALUES(504,1,'Gröt',NULL)"))
    db.execute(text("INSERT INTO menus(id,tenant_id,week,year) VALUES(601,1,:w,:y)"), {"w": WEEK, "y": YEAR})
    # Monday variants day key 'mon'
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(601,'mon','lunch','alt1',501)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(601,'mon','lunch','alt2',502)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(601,'mon','dessert','dessert',503)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(601,'mon','dinner','dinner',504)"))
    db.commit()


def test_portal_etag_no_change_304(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK, alt2_enabled_monday=1)
    seed_canonical_builder_publication(site_id=SITE_ID, year=YEAR, week=WEEK)

    url = f"/portal/department/week?year={YEAR}&week={WEEK}"
    r1 = client_admin.get(url, headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r1.status_code == 200
    etag1 = r1.headers.get("ETag")
    assert etag1
    r2 = client_admin.get(url, headers={**_h(), "If-None-Match": etag1}, environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r2.status_code == 304
    assert r2.headers.get("ETag") == etag1
    assert r2.get_data() in (b"", b"\n")


def test_portal_etag_stays_frozen_until_republish(client_admin, app_session, seed_portal_department_data, seed_canonical_builder_publication):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK, alt2_enabled_monday=1)
    composition_service = seed_canonical_builder_publication(site_id=SITE_ID, year=YEAR, week=WEEK, alt1_name="Pannbiff")

    url = f"/portal/department/week?year={YEAR}&week={WEEK}"
    r_before = client_admin.get(url, headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r_before.status_code == 200
    etag_before = r_before.headers.get("ETag")
    lunch_alt1_before = r_before.get_json()["days"][0]["menu"]["lunch_alt1"]
    assert lunch_alt1_before == "Pannbiff"

    # Change the canonical Builder composition name → the already published snapshot must stay frozen.
    with app_session.app_context():
        composition_service.update_composition_metadata("builder-alt1", composition_name="Köttbullar")

    r_after = client_admin.get(url, headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r_after.status_code == 200
    etag_after = r_after.headers.get("ETag")
    assert etag_after == etag_before
    lunch_alt1_after = r_after.get_json()["days"][0]["menu"]["lunch_alt1"]
    assert lunch_alt1_after == "Pannbiff"

    # Explicit republish creates the new immutable snapshot.
    seed_canonical_builder_publication(site_id=SITE_ID, year=YEAR, week=WEEK, alt1_name="Köttbullar")

    r_republished = client_admin.get(url, headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r_republished.status_code == 200
    etag_republished = r_republished.headers.get("ETag")
    assert etag_republished and etag_republished != etag_before
    lunch_alt1_republished = r_republished.get_json()["days"][0]["menu"]["lunch_alt1"]
    assert lunch_alt1_republished == "Köttbullar"

    # 304 check for new ETag
    r_304 = client_admin.get(url, headers={**_h(), "If-None-Match": etag_republished}, environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r_304.status_code == 304


def test_portal_etag_changes_on_selected_alt_update(client_admin, seed_portal_department_data, seed_canonical_builder_publication, seed_portal_menu_choice):
    # Start with an explicit Alt1 choice; changing the explicit choice should move the ETag.
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK, alt2_enabled_monday=0)
    seed_canonical_builder_publication(site_id=SITE_ID, year=YEAR, week=WEEK)
    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=DEPT_ID, year=YEAR, week=WEEK, weekday=1, selected_variant="Alt1")

    url = f"/portal/department/week?year={YEAR}&week={WEEK}"
    r_before = client_admin.get(url, headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r_before.status_code == 200
    payload_before = r_before.get_json()
    assert payload_before["days"][0]["choice"]["selected_alt"] == "Alt1"
    etag_before = r_before.headers.get("ETag")

    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=DEPT_ID, year=YEAR, week=WEEK, weekday=1, selected_variant="Alt2")

    r_after = client_admin.get(url, headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r_after.status_code == 200
    payload_after = r_after.get_json()
    assert payload_after["days"][0]["choice"]["selected_alt"] == "Alt2"
    etag_after = r_after.headers.get("ETag")
    assert etag_after and etag_before and etag_after != etag_before

    # 304 check after choice change
    r_304 = client_admin.get(url, headers={**_h(), "If-None-Match": etag_after}, environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r_304.status_code == 304
