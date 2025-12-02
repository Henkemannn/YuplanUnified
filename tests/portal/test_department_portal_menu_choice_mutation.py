from sqlalchemy import text

YEAR = 2025
WEEK = 47
DEPT_ID = "77777777-1111-2222-3333-999999999999"
SITE_ID = "site-aaa-bbbb"


def _h():
    return {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basic(db):
    db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT NOT NULL DEFAULT 'manual')"))
    db.execute(text("CREATE TABLE IF NOT EXISTS department_notes(department_id TEXT PRIMARY KEY, notes TEXT)"))
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:i,'site', 'Dept','manual')"), {"i": DEPT_ID})
    db.execute(text("INSERT OR REPLACE INTO department_notes(department_id, notes) VALUES(:i,'Note')"), {"i": DEPT_ID})
    # Alt2 flags storage
    db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags(site_id TEXT, department_id TEXT, week INTEGER, weekday INTEGER, enabled INTEGER, version INTEGER, UNIQUE(site_id,department_id,week,weekday))"))
    # Ensure clean slate for this department/week to avoid cross-test leakage
    db.execute(text("DELETE FROM alt2_flags WHERE department_id=:d AND week=:w"), {"d": DEPT_ID, "w": WEEK})
    db.commit()


def _get_menu_choice_etag(client):
    r = client.get(f"/portal/department/week?year={YEAR}&week={WEEK}", headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert r.status_code == 200
    return r.get_json()["etag_map"]["menu_choice"], r.get_json()


def test_menu_choice_mutation_happy_path(client_admin):
    from core.db import get_session
    db = get_session()
    try:
        _seed_basic(db)
    finally:
        db.close()
    old_etag, payload_before = _get_menu_choice_etag(client_admin)
    # Initially Alt2 not chosen for Monday
    day_map = {d["weekday_name"]: d for d in payload_before["days"]}
    assert day_map["Måndag"]["choice"]["selected_alt"] in (None, "Alt1")
    resp = client_admin.post(
        "/portal/department/menu-choice/change",
        json={"year": YEAR, "week": WEEK, "weekday": "Mon", "selected_alt": "Alt2"},
        headers={**_h(), "If-Match": old_etag},
        environ_overrides={"test_claims": {"department_id": DEPT_ID}},
    )
    assert resp.status_code == 200
    new_etag = resp.get_json()["new_etag"]
    assert new_etag != old_etag
    assert resp.get_json()["selected_alt"] == "Alt2"
    # Verify via GET
    updated_etag, payload_after = _get_menu_choice_etag(client_admin)
    assert updated_etag == new_etag
    day_map_after = {d["weekday_name"]: d for d in payload_after["days"]}
    assert day_map_after["Måndag"]["choice"]["selected_alt"] == "Alt2"


def test_menu_choice_mutation_missing_if_match(client_admin):
    from core.db import get_session
    db = get_session()
    try:
        _seed_basic(db)
    finally:
        db.close()
    resp = client_admin.post(
        "/portal/department/menu-choice/change",
        json={"year": YEAR, "week": WEEK, "weekday": "Mon", "selected_alt": "Alt2"},
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": DEPT_ID}},
    )
    assert resp.status_code == 400


def test_menu_choice_mutation_stale_etag(client_admin):
    from core.db import get_session
    db = get_session()
    try:
        _seed_basic(db)
    finally:
        db.close()
    old_etag, payload_before = _get_menu_choice_etag(client_admin)
    # First mutation valid
    resp1 = client_admin.post(
        "/portal/department/menu-choice/change",
        json={"year": YEAR, "week": WEEK, "weekday": "Mon", "selected_alt": "Alt2"},
        headers={**_h(), "If-Match": old_etag},
        environ_overrides={"test_claims": {"department_id": DEPT_ID}},
    )
    assert resp1.status_code == 200
    new_etag = resp1.get_json()["new_etag"]
    assert new_etag != old_etag
    # Second mutation with stale (old) etag should fail
    resp2 = client_admin.post(
        "/portal/department/menu-choice/change",
        json={"year": YEAR, "week": WEEK, "weekday": "Mon", "selected_alt": "Alt1"},
        headers={**_h(), "If-Match": old_etag},
        environ_overrides={"test_claims": {"department_id": DEPT_ID}},
    )
    assert resp2.status_code == 412
    # Confirm persisted stays Alt2
    _, payload_after = _get_menu_choice_etag(client_admin)
    day_map_after = {d["weekday_name"]: d for d in payload_after["days"]}
    assert day_map_after["Måndag"]["choice"]["selected_alt"] == "Alt2"
