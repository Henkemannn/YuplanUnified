import re
from datetime import date
from sqlalchemy import text
from core.db import get_session


def _ensure_basic_seed():
    db = get_session()
    try:
        # Create site if missing
        row = db.execute(text("SELECT id FROM sites WHERE id='site-demo-1'")).fetchone()
        if not row:
            db.execute(text("INSERT INTO sites(id,name) VALUES('site-demo-1','Demo Site')"))
        # Create departments
        cols = {r[1] for r in db.execute(text("PRAGMA table_info('departments')")).fetchall()}
        has_mode = "resident_count_mode" in cols
        for dep_id, dep_name in [("dept-demo-1","Avd A"),("dept-demo-2","Avd B")]:
            r = db.execute(text("SELECT id FROM departments WHERE id=:id"), {"id": dep_id}).fetchone()
            if not r:
                if has_mode:
                    db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode) VALUES(:i,'site-demo-1',:n,'manual')"), {"i": dep_id, "n": dep_name})
                else:
                    db.execute(text("INSERT INTO departments(id, site_id, name) VALUES(:i,'site-demo-1',:n)"), {"i": dep_id, "n": dep_name})
        db.commit()
    finally:
        db.close()


def test_get_renders_structure(client):
    _ensure_basic_seed()
    client.post("/test-login", data={"role": "admin", "destination": "/ui/cook"})
    d = date(2025, 11, 17)
    resp = client.get(f"/ui/planera/week?site_id=site-demo-1&year=2025&week=47&date={d.isoformat()}&meal=lunch")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Planering – vecka" in html
    assert "<table" in html and "yp-table" in html
    # Department names present
    assert "Avdelning" in html
    # Specials badge present (generic check)
    assert re.search(r"<span class=\"yp-badge\">.+:\s*\d+<", html)


def test_post_mark_all_marks_rows_done(client):
    _ensure_basic_seed()
    client.post("/test-login", data={"role": "admin", "destination": "/ui/cook"})
    d = date(2025, 11, 17)
    # Assume two demo departments
    dep_ids = ["dept-demo-1", "dept-demo-2"]
    resp = client.post(
        "/ui/planera/week/mark_all",
        data={
            "site_id": "site-demo-1",
            "date": d.isoformat(),
            "meal": "lunch",
            "department_ids": dep_ids,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Expect Klar badges after marking
    assert html.count("yp-badge--success") >= 1

def test_rbac_blocks_non_admin(client):
    _ensure_basic_seed()
    client.post("/test-login", data={"role": "viewer", "destination": "/ui/cook"})
    d = date(2025, 11, 17)
    r1 = client.get(f"/ui/planera/week?site_id=site-demo-1&year=2025&week=47&date={d.isoformat()}&meal=lunch")
    # Decorator likely returns 403 or redirects per existing patterns; accept either
    assert r1.status_code in (302, 403)
    r2 = client.post(
        "/ui/planera/week/mark_all",
        data={
            "site_id": "site-demo-1",
            "date": d.isoformat(),
            "meal": "lunch",
            "department_ids": ["dept-demo-1"],
        },
    )
    assert r2.status_code in (302, 403)
