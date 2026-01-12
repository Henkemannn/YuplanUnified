import uuid
from sqlalchemy import text

HEADERS_PORTAL = {"X-User-Role": "unit_portal", "X-Tenant-Id": "1"}


def _seed_site_dep():
    from core.db import get_session
    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep_id = str(uuid.uuid4())
        db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "PortalSite"})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',8,0)"), {"i": dep_id, "s": site_id, "n": "Avd Portal"})
        db.commit()
        return site_id, dep_id
    finally:
        db.close()


def test_rendering_reflects_saved_choice_alt2(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_dep()
    year, week = 2026, 3
    # Seed menu for Tuesday with alt1 + alt2
    from core.menu_repo import MenuRepo
    mr = MenuRepo()
    mr.upsert_menu_item(site_id, year, week, day=2, meal="lunch", alt1_text="Köttbullar", alt2_text="Fisk", dessert="Glass")
    # Save choice alt2 for Tuesday
    from core.department_menu_choices_repo import DepartmentMenuChoicesRepo
    repo = DepartmentMenuChoicesRepo(); repo.ensure_table_exists()
    repo.upsert_choice(site_id, dep_id, year, week, day=2, lunch_choice="alt2")
    # GET portal week
    r = client.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}", headers=HEADERS_PORTAL)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Radios exist and reflect saved state specifically for Tuesday
    assert 'name="choice_2"' in html
    assert 'name="choice_2" value="alt2"' in html and ('name="choice_2" value="alt2" checked' in html)
    assert ('name="choice_2" value="alt1" checked' not in html)


def test_save_flow_persists_and_renders(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_dep()
    year, week = 2026, 4
    from core.menu_repo import MenuRepo
    mr = MenuRepo()
    # Seed Tuesday alt2 available; Wednesday only alt1
    mr.upsert_menu_item(site_id, year, week, day=2, meal="lunch", alt1_text="Pasta", alt2_text="Vegetarisk", dessert="")
    mr.upsert_menu_item(site_id, year, week, day=3, meal="lunch", alt1_text="Soppa", alt2_text=None, dessert="")
    # POST choices
    form = {
        "site_id": site_id,
        "department_id": dep_id,
        "year": str(year),
        "week": str(week),
        "choice_2": "alt2",
        "choice_3": "alt1",
    }
    r = client.post("/ui/portal/week/save", data=form, headers=HEADERS_PORTAL, follow_redirects=False)
    assert r.status_code in (302, 303)
    # Verify persisted
    from core.department_menu_choices_repo import DepartmentMenuChoicesRepo
    repo = DepartmentMenuChoicesRepo()
    choices = repo.get_choices_for_week(site_id, dep_id, year, week)
    assert choices.get(2) == "alt2"
    assert choices.get(3) == "alt1"
    # GET reflects state
    r2 = client.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}", headers=HEADERS_PORTAL)
    html2 = r2.get_data(as_text=True)
    assert 'name="choice_2"' in html2 and 'value="alt2" checked' in html2
    assert 'name="choice_3"' in html2 and 'value="alt1" checked' in html2


def test_alt2_missing_guard_returns_400(app_session):
    client = app_session.test_client()
    site_id, dep_id = _seed_site_dep()
    year, week = 2026, 5
    from core.menu_repo import MenuRepo
    mr = MenuRepo()
    # Seed Monday with only alt1 (no alt2)
    mr.upsert_menu_item(site_id, year, week, day=1, meal="lunch", alt1_text="Gröt", alt2_text=None, dessert="")
    form = {
        "site_id": site_id,
        "department_id": dep_id,
        "year": str(year),
        "week": str(week),
        "choice_1": "alt2",
    }
    r = client.post("/ui/portal/week/save", data=form, headers=HEADERS_PORTAL)
    assert r.status_code == 400
    # Verify not persisted
    from core.department_menu_choices_repo import DepartmentMenuChoicesRepo
    repo = DepartmentMenuChoicesRepo()
    choices = repo.get_choices_for_week(site_id, dep_id, year, week)
    assert choices.get(1) is None
