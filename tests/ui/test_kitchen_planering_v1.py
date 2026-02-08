import pytest
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        # Robust insert: avoid collisions on unique name or id
        conn.execute(
            text("INSERT OR IGNORE INTO sites (id, name) VALUES (:id, :name)"),
            {"id": "00000000-0000-0000-0000-000000000000", "name": "Test Site"},
        )
        conn.commit()
    finally:
        conn.close()


def test_planering_v1_empty_state(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Välj dag och måltid" in html


def test_planering_v1_selected_state(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    # Seed a department and a diet type with defaults so the checklist has options
    from core.admin_repo import DepartmentsRepo, DietTypesRepo
    from core.db import get_session
    # Robust department seeding: tolerate pre-existing rows by name within the same site
    db = get_session()
    try:
        # Ensure table exists for sqlite dev/test fallback
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id TEXT PRIMARY KEY,
                site_id TEXT NOT NULL,
                name TEXT NOT NULL,
                resident_count_mode TEXT NOT NULL,
                resident_count_fixed INTEGER NOT NULL DEFAULT 0,
                notes TEXT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT
            )
            """
        ))
        dept_id = "dep-planering-v1"
        db.execute(
            text(
                """
                INSERT OR IGNORE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version)
                VALUES(:i, :s, :n, 'fixed', :rc, 0)
                """
            ),
            {"i": dept_id, "s": site_id, "n": "Avd 1", "rc": 10},
        )
        row = db.execute(text("SELECT id FROM departments WHERE site_id=:s AND name=:n"), {"s": site_id, "n": "Avd 1"}).fetchone()
        dep_id_out = row[0]
        db.commit()
    finally:
        db.close()
    drepo = DepartmentsRepo()
    dep = {"id": dep_id_out, "site_id": site_id, "name": "Avd 1"}
    trepo = DietTypesRepo()
    dt_id = trepo.create(site_id=site_id, name="Glutenfri", default_select=False)
    ver = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], ver, [{"diet_type_id": str(dt_id), "default_count": 3}])

    # First request: selected day+meal should render checklist UI immediately (wizard step 3)
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Tillagningslista" in html
    assert "js-special-chip" in html
    assert "data-diet-id" in html

    # Second request: with a selected diet, adaptation list should render
    rv2 = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch&selected_diets={dt_id}", headers=HEADERS)
    assert rv2.status_code == 200
    html2 = rv2.data.decode("utf-8")
    assert "Anpassningslista" in html2
    assert "Avd 1" in html2
