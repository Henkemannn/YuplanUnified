from datetime import date as _date
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_bulk():
    from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
    srepo = SitesRepo()
    site, _ = srepo.create_site("Bulk Site")
    site_id = site["id"]
    drepo = DepartmentsRepo()
    dep_a, _ = drepo.create_department(site_id, "Avd A", "fixed", 10)
    dep_b, _ = drepo.create_department(site_id, "Avd B", "fixed", 8)
    trepo = DietTypesRepo()
    dt_gluten = trepo.create(site_id=site_id, name="Glutenfri", default_select=False)
    dt_laktos = trepo.create(site_id=site_id, name="Laktosfri", default_select=False)
    v_a = drepo.get_version(dep_a["id"]) or 0
    v_b = drepo.get_version(dep_b["id"]) or 0
    drepo.upsert_department_diet_defaults(dep_a["id"], v_a, [
        {"diet_type_id": str(dt_gluten), "default_count": 2},
        {"diet_type_id": str(dt_laktos), "default_count": 1},
    ])
    drepo.upsert_department_diet_defaults(dep_b["id"], v_b, [
        {"diet_type_id": str(dt_gluten), "default_count": 3},
        {"diet_type_id": str(dt_laktos), "default_count": 2},
    ])
    return {
        "site_id": site_id,
        "deps": [dep_a["id"], dep_b["id"]],
        "diet_ids": [str(dt_gluten), str(dt_laktos)],
    }


def test_bulk_mark_produced_updates_weekview(app_session):
    client = app_session.test_client()
    seeded = _seed_bulk()
    site_id = seeded["site_id"]
    today = _date.today()
    year = today.year
    week = today.isocalendar()[1]
    payload = {
        "site_id": site_id,
        "year": year,
        "week": week,
        "day_index": 0,
        "meal": "lunch",
        "selected_diet_type_ids": seeded["diet_ids"],
    }
    rv = client.post("/api/planering/mark_produced_special", json=payload, headers=HEADERS)
    assert rv.status_code == 200
    data = rv.get_json()
    assert data and data.get("ok") is True
    # Verify registrations marked in weekview_registrations
    from core.db import get_session
    db = get_session()
    try:
        rows = db.execute(text(
            """
            SELECT COUNT(*) FROM weekview_registrations
            WHERE tenant_id=:tid AND year=:y AND week=:w AND day_of_week=:d AND meal=:m AND marked=1
            """
        ), {"tid": "1", "y": year, "w": week, "d": 1, "m": "lunch"}).fetchone()
        count = int(rows[0] or 0) if rows else 0
    finally:
        db.close()
    # 2 departments x 2 diets = 4 marks
    assert count == 4
