from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _ensure_site_and_diet(site_id: str) -> str:
    from core.admin_repo import SitesRepo, DietTypesRepo
    srepo = SitesRepo(); srepo.create_site("Toggle Site")
    trepo = DietTypesRepo()
    diet_id = trepo.create(site_id=site_id, name="Laktos", default_select=False)
    return str(diet_id)


def test_toggle_normal_exclusion_insert_then_remove(app_session):
    client = app_session.test_client()
    site_id = "site-normal-exc-1"
    diet_id = _ensure_site_and_diet(site_id)
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS normal_exclusions (
              tenant_id TEXT NOT NULL,
              site_id TEXT NOT NULL,
              year INTEGER NOT NULL,
              week INTEGER NOT NULL,
              day_index INTEGER NOT NULL,
              meal TEXT NOT NULL,
              alt TEXT NOT NULL,
              diet_type_id TEXT NOT NULL,
              UNIQUE (tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
            );
            """
        ))
        db.commit()
    finally:
        db.close()

    payload = {
        "site_id": site_id,
        "year": 2026,
        "week": 6,
        "day_index": 3,
        "meal": "lunch",
        "alt": "1",
        "diet_type_id": diet_id,
    }
    # First toggle -> insert
    rv = client.post("/api/kitchen/planering/normal_exclusions/toggle", json=payload, headers=HEADERS)
    assert rv.status_code == 200
    data = rv.get_json()
    assert data and data.get("excluded") is True
    # Verify row exists
    db = get_session()
    try:
        row = db.execute(text(
            "SELECT COUNT(1) FROM normal_exclusions WHERE tenant_id=:tid AND site_id=:s AND year=:y AND week=:w AND day_index=:d AND meal=:m AND alt=:a AND diet_type_id=:dt"
        ), {"tid": "1", "s": site_id, "y": 2026, "w": 6, "d": 3, "m": "lunch", "a": "1", "dt": diet_id}).fetchone()
        assert int(row[0]) == 1
    finally:
        db.close()

    # Second toggle -> delete
    rv2 = client.post("/api/kitchen/planering/normal_exclusions/toggle", json=payload, headers=HEADERS)
    assert rv2.status_code == 200
    data2 = rv2.get_json()
    assert data2 and data2.get("excluded") is False
    # Verify row removed
    db = get_session()
    try:
        row2 = db.execute(text(
            "SELECT COUNT(1) FROM normal_exclusions WHERE tenant_id=:tid AND site_id=:s AND year=:y AND week=:w AND day_index=:d AND meal=:m AND alt=:a AND diet_type_id=:dt"
        ), {"tid": "1", "s": site_id, "y": 2026, "w": 6, "d": 3, "m": "lunch", "a": "1", "dt": diet_id}).fetchone()
        assert int(row2[0]) == 0
    finally:
        db.close()
