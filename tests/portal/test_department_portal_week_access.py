from datetime import date as _date
from datetime import datetime
import pytest
from sqlalchemy import text

from core.db import get_session
from portal.department.auth import DepartmentPortalScope
from portal.department.service import build_department_week_payload


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _seed_portal_week(db, dept_id: str, site_id: str, year: int, week: int):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments(
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT,
            notes TEXT NULL,
            resident_count_mode TEXT NOT NULL DEFAULT 'manual'
        )
    """))
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, notes, resident_count_mode) VALUES(:i,:s,:n,:note,'manual')"), {"i": dept_id, "s": site_id, "n": "Avd 1", "note": "Inga risrätter"})
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_registrations(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal,diet_type))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_residents_count(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, count INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week,meal))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_alt2_flags(tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, is_alt2 INTEGER, UNIQUE(tenant_id,department_id,year,week,day_of_week))"))
    db.execute(text("INSERT INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'lunch',10)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_residents_count VALUES(:t,:d,:y,:w,1,'dinner',8)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Gluten',1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_registrations VALUES(:t,:d,:y,:w,1,'lunch','Laktos',1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_alt2_flags VALUES(:t,:d,:y,:w,1,1)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("INSERT INTO weekview_residents_count VALUES(:t,:d,:y,:w,2,'lunch',12)"), {"t": 1, "d": dept_id, "y": year, "w": week})
    db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"))
    db.execute(text("INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,1,1,1)"), {"s": site_id, "d": dept_id, "w": week})
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO tenants(id,name,active) VALUES(1,'Demo',1)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS dishes(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, name TEXT, category TEXT)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, week INTEGER, year INTEGER)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS menu_variants(id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL, day TEXT, meal TEXT, variant_type TEXT, dish_id INTEGER)"))
    db.execute(text("DELETE FROM menu_variants WHERE menu_id=201"))
    db.execute(text("DELETE FROM menus WHERE id=201"))
    db.execute(text("DELETE FROM dishes WHERE id IN (101,102,103,104)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(101,1,'Pannbiff med lök',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(102,1,'Fiskgratäng',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(103,1,'Fruktsallad',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO dishes(id,tenant_id,name,category) VALUES(104,1,'Kvällsgröt',NULL)"))
    db.execute(text("INSERT OR REPLACE INTO menus(id,tenant_id,week,year) VALUES(201,1,:w,:y)"), {"w": week, "y": year})
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(201,'mon','lunch','alt1',101)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(201,'mon','lunch','alt2',102)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(201,'mon','dessert','dessert',103)"))
    db.execute(text("INSERT INTO menu_variants(menu_id,day,meal,variant_type,dish_id) VALUES(201,'mon','dinner','dinner',104)"))
    db.commit()


def test_portal_week_endpoint_populate(client_admin, app_session, seed_portal_department_data, seed_canonical_builder_publication, seed_portal_menu_choice):
    year = 2025
    week = 47
    dept_id = "11111111-2222-3333-4444-555555555555"
    site_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=year, week=week)
    seed_canonical_builder_publication(
        site_id=site_id,
        year=year,
        week=week,
        alt1_name="Pannbiff med lök",
        alt2_name="Fiskgratäng",
        dessert_name="Fruktsallad",
        dinner_name="Kvällsgröt",
    )
    seed_portal_menu_choice(
        tenant_id=1,
        site_id=site_id,
        department_id=dept_id,
        year=year,
        week=week,
        weekday=1,
        selected_variant="Alt2",
    )
    seed_portal_menu_choice(
        tenant_id=1,
        site_id=site_id,
        department_id=dept_id,
        year=year,
        week=week,
        weekday=2,
        selected_variant="Alt1",
    )
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    r1 = client_admin.get(
        f"/portal/department/week?year={year}&week={week}",
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    data = r1.get_json()
    assert data["department_id"] == dept_id
    assert data["facts"]["note"] == "Inga risrätter"
    assert data["progress"]["total_days"] == 7
    monday = data["days"][0]
    assert monday["flags"]["alt2_lunch"] is True
    assert monday["choice"]["selected_alt"] == "Alt2"
    lunch_diets = monday["diets_summary"]["lunch"]
    diet_names = {d["diet_name"] for d in lunch_diets}
    assert {"Gluten", "Laktos"}.issubset(diet_names)
    menu_mon = monday["menu"]
    assert menu_mon["lunch_alt1"] == "Pannbiff med lök"
    assert menu_mon["lunch_alt2"] == "Fiskgratäng"
    assert menu_mon["dessert"] == "Fruktsallad"
    assert menu_mon["dinner"] == "Kvällsgröt"
    tuesday = data["days"][1]
    assert tuesday["choice"]["selected_alt"] == "Alt1"
    assert tuesday["diets_summary"]["lunch"] == []
    menu_tue = tuesday["menu"]
    assert menu_tue["lunch_alt1"] is None
    assert menu_tue["lunch_alt2"] is None
    assert menu_tue["dessert"] is None
    assert menu_tue["dinner"] is None
    assert data["progress"]["days_with_choice"] >= 1
    assert etag and etag.startswith('W/"portal-dept-week:')
    r2 = client_admin.get(
        f"/portal/department/week?year={year}&week={week}",
        headers={**_h(), "If-None-Match": etag},
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert r2.status_code == 304
    assert r2.get_data() in (b"", b"\n")
    assert r2.headers.get("ETag") == etag


def test_portal_week_endpoint_reads_departments_notes_without_department_notes_table(
    client_admin,
    seed_portal_department_data,
    seed_canonical_builder_publication,
):
    year = 2025
    week = 47
    dept_id = "77777777-8888-9999-aaaa-bbbbbbbbbbbb"
    site_id = "cccccccc-dddd-eeee-ffff-111111111111"
    seed_portal_department_data(
        dept_id=dept_id,
        site_id=site_id,
        year=year,
        week=week,
        note="Department note from departments",
    )
    seed_canonical_builder_publication(site_id=site_id, year=year, week=week)

    with client_admin.application.app_context():
        db = get_session()
        try:
            table_row = db.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='department_notes'")
            ).fetchone()
            assert table_row is None
        finally:
            db.close()

    resp = client_admin.get(
        f"/ui/portal/department/week?year={year}&week={week}",
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Department note from departments" in html


def test_portal_week_endpoint_empty_department_note_is_empty_string(
    client_admin,
    seed_portal_department_data,
    seed_canonical_builder_publication,
):
    year = 2025
    week = 47
    dept_id = "88888888-9999-aaaa-bbbb-cccccccccccc"
    site_id = "dddddddd-eeee-ffff-0000-222222222222"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=year, week=week, note="")
    seed_canonical_builder_publication(site_id=site_id, year=year, week=week)

    resp = client_admin.get(
        f"/portal/department/week?year={year}&week={week}",
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["facts"]["note"] == ""


def test_portal_week_payload_unknown_department_is_controlled(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    year = 2025
    week = 47
    dept_id = "99999999-aaaa-bbbb-cccc-dddddddddddd"
    site_id = "eeeeeeee-ffff-0000-1111-222222222222"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=year, week=week)
    seed_canonical_builder_publication(site_id=site_id, year=year, week=week)

    scope = DepartmentPortalScope(user_id=1, role="admin", tenant_id=1, department_id="missing-dept", site_id=site_id)
    with pytest.raises(ValueError, match="department_not_found"):
        build_department_week_payload(scope, year, week)


def test_portal_week_basic_access(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    dept_id = "55555555-2222-3333-4444-111111111111"
    site_id = "zzzzzzzz-bbbb-cccc-dddd-yyyyyyyyyyyy"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=2025, week=47)
    seed_canonical_builder_publication(site_id=site_id, year=2025, week=47)
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    resp_ok = client_admin.get(
        "/portal/department/week?year=2025&week=47",
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp_ok.status_code == 200


def test_portal_week_without_publication_has_empty_menu(client_admin, seed_portal_department_data):
    year = 2025
    week = 47
    dept_id = "66666666-7777-8888-9999-000000000000"
    site_id = "ffffffff-eeee-dddd-cccc-bbbbbbbbbbbb"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=year, week=week)
    resp = client_admin.get(
        f"/portal/department/week?year={year}&week={week}",
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    monday = payload["days"][0]
    assert monday["menu"]["lunch_alt1"] is None
    assert monday["menu"]["lunch_alt2"] is None
    assert monday["menu"]["dessert"] is None
    assert monday["menu"]["dinner"] is None


@pytest.mark.parametrize(
    ("year", "week", "expected_monday", "expected_sunday"),
    [
        (2026, 35, "2026-08-24", "2026-08-30"),
        (2026, 36, "2026-08-31", "2026-09-06"),
        (2026, 1, "2025-12-29", "2026-01-04"),
        (2020, 53, "2020-12-28", "2021-01-03"),
    ],
)
def test_portal_week_iso_dates_are_aligned(client_admin, seed_portal_department_data, seed_canonical_builder_publication, year, week, expected_monday, expected_sunday):
    dept_id = f"iso-{year}-{week}-dept"
    site_id = f"iso-{year}-{week}-site"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=year, week=week)
    seed_canonical_builder_publication(site_id=site_id, year=year, week=week)

    resp = client_admin.get(
        f"/portal/department/week?year={year}&week={week}",
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    expected_dates = [_date.fromisocalendar(year, week, dow).isoformat() for dow in range(1, 8)]
    actual_dates = [day["date"] for day in payload["days"]]
    assert actual_dates == expected_dates
    assert actual_dates[0] == expected_monday
    assert actual_dates[-1] == expected_sunday
    assert payload["week"] == week
    assert payload["year"] == year


def test_portal_week_iso_dates_rendered_html_matches_payload(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    year = 2026
    week = 35
    dept_id = "iso-render-dept"
    site_id = "iso-render-site"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=year, week=week)
    seed_canonical_builder_publication(site_id=site_id, year=year, week=week)

    resp = client_admin.get(
        f"/ui/portal/department/week?year={year}&week={week}",
        environ_overrides={"test_claims": {"department_id": dept_id}},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Vecka 35" in html
    for dow in range(1, 8):
        assert _date.fromisocalendar(year, week, dow).isoformat() in html