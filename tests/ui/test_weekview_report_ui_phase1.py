import re
from flask.testing import FlaskClient
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session


def _seed_site_with_departments(db, site_id: str, dep_pairs: list[tuple[str, str]]):
    if not db.execute(text("SELECT 1 FROM sites WHERE id=:i"), {"i": site_id}).fetchone():
        db.execute(text("INSERT INTO sites(id,name) VALUES(:i,:n)"), {"i": site_id, "n": "Test Site"})
    for dep_id, dep_name in dep_pairs:
        if not db.execute(text("SELECT 1 FROM departments WHERE id=:i"), {"i": dep_id}).fetchone():
            # Detect schema columns and insert accordingly
            cols = {r[1] for r in db.execute(text("PRAGMA table_info('departments')")).fetchall()}
            if {"resident_count_mode", "resident_count_fixed"}.issubset(cols):
                db.execute(
                    text(
                        "INSERT INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed) "
                        "VALUES(:i,:s,:n,'fixed',0)"
                    ),
                    {"i": dep_id, "s": site_id, "n": dep_name},
                )
            else:
                db.execute(text("INSERT INTO departments(id,site_id,name) VALUES(:i,:s,:n)"), {"i": dep_id, "s": site_id, "n": dep_name})
    db.commit()


def test_weekview_report_basic_structure():
    app = create_app()
    app.config.update({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            site_id = "site-test-1"
            deps = [("dep-a", "Avd A"), ("dep-b", "Avd B")]
            _seed_site_with_departments(db, site_id, deps)
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    # Inject role/tenant for UI access
    resp = client.get(
        f"/ui/reports/weekview?site_id={site_id}&year=2025&week=49",
        headers={"X-User-Role": "cook", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    # Header assertions
    assert "Veckorapport" in html
    assert re.search(r"År\s+2025\s+•\s+Vecka\s+49", html)
    # Departments present
    assert "Avd A" in html
    assert "Avd B" in html
    # Table headers (Swedish)
    assert "Lunch – Boende" in html
    assert "Middag – Boende" in html
    # Totals row per department and global summary
    assert "Totalt" in html
    # Basic presence of global summary labels
    assert "Totalt boende (lunch):" in html
    assert "Totalt boende (middag):" in html
