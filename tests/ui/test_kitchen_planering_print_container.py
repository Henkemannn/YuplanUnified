import re
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_minimal(site_id: str):
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0)"))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name, version) VALUES(:i,'Test Site',0)"), {"i": site_id})
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS departments (
              id TEXT PRIMARY KEY,
              site_id TEXT NOT NULL,
              name TEXT NOT NULL,
              resident_count_mode TEXT NOT NULL,
              resident_count_fixed INTEGER NOT NULL DEFAULT 0,
              notes TEXT NULL,
              version INTEGER NOT NULL DEFAULT 0
            )
            """
        ))
        db.execute(text(
            "INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version)\n             VALUES(:id, :s, 'Avd 1', 'fixed', 10, 0)"
        ), {"id": "dept-print-1", "s": site_id})
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
              site_id TEXT NOT NULL,
              department_id TEXT NOT NULL,
              year INTEGER NOT NULL,
              week INTEGER NOT NULL,
              day_of_week INTEGER NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 0,
              UNIQUE (site_id, department_id, year, week, day_of_week)
            )
            """
        ))
        db.commit()
    finally:
        db.close()


def test_print_container_present_and_clean(app_session):
    client = app_session.test_client()
    site_id = "site-plan-print"
    _seed_minimal(site_id)
    db = None
    try:
        from core.db import get_session
        db = get_session()
        db.execute(text(
            "INSERT OR REPLACE INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled)\n             VALUES(:s, :d, :y, :w, 1, 1)"
        ), {"s": site_id, "d": "dept-print-1", "y": 2026, "w": 6})
        db.commit()
    finally:
        if db is not None:
            db.close()
    base = f"/ui/kitchen/planering?site_id={site_id}&year=2026&week=6&day=0&meal=lunch&mode=special"

    rv = client.get(base + "&print_mode=normal", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "id=\"yp-print-root\"" in html
    root_idx = html.find("id=\"yp-print-root\"")
    assert root_idx != -1
    assert html.find("kp-print-sheet", root_idx) != -1
    assert html.find("Normalkost", root_idx) != -1
    assert html.find("kp-altpill", root_idx) == -1
    assert html.find("kp-zebra", root_idx) != -1
    assert html.find("Vald specialkost", root_idx) == -1
    assert html.find("Gult = Alt 2 vald", root_idx) == -1

    rv2 = client.get(base + "&print_mode=special", headers=HEADERS)
    assert rv2.status_code == 200
    html2 = rv2.data.decode("utf-8")
    root_idx2 = html2.find("id=\"yp-print-root\"")
    assert root_idx2 != -1
    assert html2.find("kp-print-sheet", root_idx2) != -1
    assert html2.find("Specialkost", root_idx2) != -1
    assert html2.find("Vald specialkost", root_idx2) != -1
    assert html2.find("Normalkost", root_idx2) == -1
    assert html2.find("kp-altpill", root_idx2) != -1
    assert html2.find("Alt2", root_idx2) != -1
    assert html2.find("class=\"count\">2", root_idx2) != -1
    assert html2.find("kp-zebra", root_idx2) != -1
    assert html2.find("kp-print-special-name kp-zebra", root_idx2) == -1
    assert html2.find("sk-card", root_idx2) != -1
    assert html2.find("sk-card", root_idx2) < html2.find("kp-print-row", root_idx2)

    rv3 = client.get(base + "&print_mode=full", headers=HEADERS)
    assert rv3.status_code == 200
    html3 = rv3.data.decode("utf-8")
    root_idx3 = html3.find("id=\"yp-print-root\"")
    assert root_idx3 != -1
    assert html3.find("kp-print-sheet", root_idx3) != -1
    assert html3.find("Normalkost", root_idx3) != -1
    assert html3.find("Specialkost", root_idx3) != -1

    rv4 = client.get(base + "&print_mode=modal", headers=HEADERS)
    assert rv4.status_code == 200
    html4 = rv4.data.decode("utf-8")
    root_idx4 = html4.find("id=\"yp-print-root\"")
    assert root_idx4 != -1
    assert html4.find("kp-print-sheet", root_idx4) != -1
    assert html4.find("Sammanfattning per boende", root_idx4) != -1
    assert html4.find("Normalkost", root_idx4) == -1
    assert html4.find("Vald specialkost", root_idx4) == -1
