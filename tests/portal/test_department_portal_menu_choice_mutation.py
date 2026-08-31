from sqlalchemy import text
from portal.department.menu_choice_repo import MenuChoiceRepo

YEAR = 2025
WEEK = 47
DEPT_ID = "77777777-1111-2222-3333-999999999999"
SITE_ID = "site-aaa-bbbb"


def _h():
    return {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basic(db):
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, notes, resident_count_mode) VALUES(:i,:s, 'Dept','Note','manual')"), {"i": DEPT_ID, "s": SITE_ID})
    # Ensure clean slate for this department/week to avoid cross-test leakage
    db.execute(text("DELETE FROM alt2_flags WHERE department_id=:d AND week=:w"), {"d": DEPT_ID, "w": WEEK})
    db.execute(text("DELETE FROM department_menu_choices WHERE department_id=:d AND year=:y AND week=:w"), {"d": DEPT_ID, "y": YEAR, "w": WEEK})
    db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id,'Portal Site',1,0)"), {"id": SITE_ID})
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


def test_menu_choice_mutation_persists_reload_counts_and_reflects_canonical_weekview_alt2(client_admin):
    from core.db import get_session

    db = get_session()
    try:
        _seed_basic(db)
    finally:
        db.close()

    repo = MenuChoiceRepo()
    etag_before, payload_before = _get_menu_choice_etag(client_admin)
    site_id = payload_before["site_id"]
    assert payload_before["progress"]["days_with_choice"] == 0
    assert payload_before["progress"]["total_days"] == 7
    assert payload_before["days"][0]["flags"]["alt2_lunch"] is False

    monday_resp = client_admin.post(
        "/portal/department/menu-choice/change",
        json={"year": YEAR, "week": WEEK, "weekday": "Mon", "selected_alt": "Alt2"},
        headers={**_h(), "If-Match": etag_before},
        environ_overrides={"test_claims": {"department_id": DEPT_ID}},
    )
    assert monday_resp.status_code == 200
    etag_after_monday = monday_resp.get_json()["new_etag"]

    rows_after_monday = repo.list_for_department_week(
        tenant_id=1,
        site_id=site_id,
        department_id=DEPT_ID,
        year=YEAR,
        week=WEEK,
    )
    assert [(row.weekday, row.selected_variant) for row in rows_after_monday] == [(1, "alt2")]

    _, payload_after_monday = _get_menu_choice_etag(client_admin)
    assert payload_after_monday["days"][0]["choice"]["selected_alt"] == "Alt2"
    assert payload_after_monday["days"][0]["flags"]["alt2_lunch"] is True
    assert payload_after_monday["progress"]["days_with_choice"] == 1
    assert payload_after_monday["progress"]["total_days"] == 7

    tuesday_resp = client_admin.post(
        "/portal/department/menu-choice/change",
        json={"year": YEAR, "week": WEEK, "weekday": "Tue", "selected_alt": "Alt1"},
        headers={**_h(), "If-Match": etag_after_monday},
        environ_overrides={"test_claims": {"department_id": DEPT_ID}},
    )
    assert tuesday_resp.status_code == 200

    rows_after_tuesday = repo.list_for_department_week(
        tenant_id=1,
        site_id=site_id,
        department_id=DEPT_ID,
        year=YEAR,
        week=WEEK,
    )
    assert [(row.weekday, row.selected_variant) for row in rows_after_tuesday] == [(1, "alt2"), (2, "alt1")]

    _, payload_after_tuesday = _get_menu_choice_etag(client_admin)
    assert payload_after_tuesday["days"][0]["choice"]["selected_alt"] == "Alt2"
    assert payload_after_tuesday["days"][1]["choice"]["selected_alt"] == "Alt1"
    assert payload_after_tuesday["days"][1]["flags"]["alt2_lunch"] is False
    assert payload_after_tuesday["progress"]["days_with_choice"] == 2
    assert payload_after_tuesday["progress"]["total_days"] == 7
