from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_unknown_diet(site_id: str) -> int:
    # Insert an invalid dietary type directly (empty name) bypassing repo guard
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS dietary_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NULL,
                site_id TEXT NULL,
                name TEXT NOT NULL,
                default_select INTEGER NOT NULL DEFAULT 0
            )
            """
        ))
        # Detect if tenant_id is NOT NULL
        cols = db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()
        notnull = {str(r[1]): int(r[3] or 0) for r in cols}
        if notnull.get('tenant_id', 0):
            db.execute(text("INSERT INTO dietary_types(tenant_id, site_id, name, default_select) VALUES(:t, :s, :n, 0)"), {"t": 1, "s": site_id, "n": ""})
        else:
            db.execute(text("INSERT INTO dietary_types(site_id, name, default_select) VALUES(:s, :n, 0)"), {"s": site_id, "n": ""})
        row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
        db.commit()
        return int(row[0]) if row else 0
    finally:
        db.close()


def test_unknown_diet_fallback_and_disabled(app_session):
    from core.admin_repo import SitesRepo, DepartmentsRepo
    srepo = SitesRepo(); site, _ = srepo.create_site("Unknown Diet Site")
    site_id = site["id"]
    drepo = DepartmentsRepo(); dep, _ = drepo.create_department(site_id, "Avd U", "fixed", 5)
    # Seed invalid diet type
    dt_id = _seed_unknown_diet(site_id)
    # Ensure it appears in diet_options by giving a default count
    v = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], v, [{"diet_type_id": str(dt_id), "default_count": 2}])

    client = app_session.test_client()
    year = 2026; week = 6; day_index = 1
    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day={day_index}&meal=lunch",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Fallback label should appear and button should be disabled
    assert f"Okänd kosttyp (#{dt_id})" in html
    assert f"data-diet-id=\"{dt_id}\"" in html
    # Disabled attribute present on chip
    idx = html.find(f"data-diet-id=\"{dt_id}\"")
    assert idx != -1
    snippet = html[max(0, idx-120):idx+200]
    assert "disabled" in snippet
