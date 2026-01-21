import uuid
from sqlalchemy import text
from core.app_factory import create_app
from core.db import get_session, create_all
from core.admin_repo import Alt2Repo


def _mk_app():
    app = create_app({"TESTING": True})
    with app.app_context():
        create_all()
    return app


def test_alt2_list_for_week_is_site_scoped(app_session):
    app = app_session
    with app.app_context():
        db = get_session()
        # Ensure base tables
        create_all()
        # Seed two sites and departments
        site_a = f"site-{uuid.uuid4()}"
        site_b = f"site-{uuid.uuid4()}"
        dep_a = f"dept-{uuid.uuid4()}"
        dep_b = f"dept-{uuid.uuid4()}"
        db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER DEFAULT 0)"))
        db.execute(text("CREATE TABLE IF NOT EXISTS departments (id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT NOT NULL, resident_count_mode TEXT DEFAULT 'fixed', resident_count_fixed INTEGER DEFAULT 0, version INTEGER DEFAULT 0)"))
        db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,:n,0)"), {"i": site_a, "n": "Site A"})
        db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,:n,0)"), {"i": site_b, "n": "Site B"})
        db.execute(text("INSERT INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES(:i,:s,:n,'fixed',10,0)"), {"i": dep_a, "s": site_a, "n": "Dept A"})
        db.execute(text("INSERT INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES(:i,:s,:n,'fixed',10,0)"), {"i": dep_b, "s": site_b, "n": "Dept B"})
        db.commit()
        repo = Alt2Repo()
        week = 42
        # Upsert flags for A and B
        repo.bulk_upsert([
            {"site_id": site_a, "department_id": dep_a, "week": week, "weekday": 1, "enabled": True},
            {"site_id": site_b, "department_id": dep_b, "week": week, "weekday": 2, "enabled": True},
        ])
        # List for site A should not include site B rows
        rows_a = repo.list_for_week(week, site_id=site_a)
        assert all(r["site_id"] == site_a for r in rows_a)
        ids_a = {(r["department_id"], r["weekday"]) for r in rows_a}
        assert (dep_b, 2) not in ids_a
        # List for site B should not include site A rows
        rows_b = repo.list_for_week(week, site_id=site_b)
        assert all(r["site_id"] == site_b for r in rows_b)
        ids_b = {(r["department_id"], r["weekday"]) for r in rows_b}
        assert (dep_a, 1) not in ids_b
        # Version is computed per site
        v_a = repo.collection_version(week, site_id=site_a)
        v_b = repo.collection_version(week, site_id=site_b)
        assert isinstance(v_a, int) and isinstance(v_b, int)
        assert v_a >= 0 and v_b >= 0
