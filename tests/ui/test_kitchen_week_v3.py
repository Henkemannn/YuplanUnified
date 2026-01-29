from flask.testing import FlaskClient
from sqlalchemy import text
from datetime import date as _date

from core.app_factory import create_app
from core.db import get_session
from core.admin_repo import DietTypesRepo, Alt2Repo


def _seed_site_and_departments(db, site_id: str, deps: list[tuple[str, str, int]]):
    if not db.execute(text("SELECT 1 FROM sites WHERE id=:i"), {"i": site_id}).fetchone():
        db.execute(text("INSERT INTO sites(id,name) VALUES(:i,:n)"), {"i": site_id, "n": f"K3 {site_id}"})
    cols = {r[1] for r in db.execute(text("PRAGMA table_info('departments')")).fetchall()}
    for dep_id, dep_name, rc in deps:
        if not db.execute(text("SELECT 1 FROM departments WHERE id=:i"), {"i": dep_id}).fetchone():
            if {"resident_count_mode", "resident_count_fixed", "version"}.issubset(cols):
                db.execute(
                    text("INSERT INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES(:i,:s,:n,'fixed',:c,0)"),
                    {"i": dep_id, "s": site_id, "n": dep_name, "c": int(rc)},
                )
            else:
                db.execute(text("INSERT INTO departments(id,site_id,name) VALUES(:i,:s,:n)"), {"i": dep_id, "s": site_id, "n": dep_name})
    db.commit()


def _link_diets(db, dept_id: str, items: list[tuple[str, int]]):
    # Create table if missing
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS department_diet_defaults (
            department_id TEXT NOT NULL,
            diet_type_id TEXT NOT NULL,
            default_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (department_id, diet_type_id)
        )
    """))
    for diet_type_id, default_count in items:
        db.execute(
            text("""
                INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count)
                VALUES(:d,:t,:c)
                ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count
            """),
            {"d": dept_id, "t": str(diet_type_id), "c": int(default_count)},
        )
    db.commit()


def test_kitchen_week_v3_renders_and_flags():
    app = create_app()
    app.config.update({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            site_id = "site-k3"
            dep1 = ("dep-1", "Avd Ett", 12)
            dep2 = ("dep-2", "Avd Två", 9)
            _seed_site_and_departments(db, site_id, [dep1, dep2])
            # Create diet types
            dt_repo = DietTypesRepo()
            dt1 = dt_repo.create(site_id=site_id, name="Glutenfri", default_select=False)
            dt2 = dt_repo.create(site_id=site_id, name="Laktosfri", default_select=False)
            # Link dt1 only to dep1; dt2 only to dep2
            _link_diets(db, dep1[0], [(dt1, 2)])
            _link_diets(db, dep2[0], [(dt2, 1)])
            # Seed an alt2 lunch flag for dep1, week 5, Monday
            Alt2Repo().bulk_upsert([{"site_id": site_id, "department_id": dep1[0], "week": 5, "weekday": 1, "enabled": True}])
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    # Ensure session site context points to our seeded site
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
    rv = client.get(f"/ui/kitchen/week?year=2026&week=5", headers=headers)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Both department names and resident counts
    assert "Avd Ett" in html and "12 boende" in html
    assert "Avd Två" in html and "9 boende" in html
    # Diet names scoped per department
    assert "Glutenfri" in html
    assert "Laktosfri" in html
    # Buttons contain dataset attributes
    assert "class=\"kostcell-btn" in html and "data-department-id" in html and "data-diet-type-id" in html
    # Alt2 flag appears at least once (Monday lunch for dep1)
    assert "is-alt2" in html


def test_kitchen_week_v3_mark_toggle():
    app = create_app()
    app.config.update({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            site_id = "site-k3b"
            dep = ("dep-3", "Avd Tre", 10)
            _seed_site_and_departments(db, site_id, [dep])
            dt_repo = DietTypesRepo()
            dt = dt_repo.create(site_id=site_id, name="Glutenfri", default_select=False)
            _link_diets(db, dep[0], [(dt, 2)])
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    # Get page
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
    rv = client.get(f"/ui/kitchen/week?year=2026&week=6", headers=headers)
    assert rv.status_code == 200
    # Fetch ETag and mark Monday lunch
    etag_resp = client.get(f"/api/weekview/etag?department_id={dep[0]}&year=2026&week=6", headers=headers)
    assert etag_resp.status_code == 200
    etag = etag_resp.get_json().get("etag")
    assert etag
    payload = {
        "year": 2026,
        "week": 6,
        "department_id": dep[0],
        "diet_type_id": str(dt),
        "meal": "lunch",
        "weekday_abbr": "Mån",
        "marked": True,
    }
    resp2 = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**headers, "If-Match": etag})
    assert resp2.status_code in (200, 412)
    # Refresh page and expect is-done class to appear at least once
    rv2 = client.get(f"/ui/kitchen/week?year=2026&week=6", headers=headers)
    assert rv2.status_code == 200
    html2 = rv2.data.decode("utf-8")
    assert "is-done" in html2
