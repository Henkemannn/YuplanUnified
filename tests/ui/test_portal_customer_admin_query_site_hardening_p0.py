import uuid
from sqlalchemy import text
from datetime import date as _date

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_two_sites(app):
    from core.db import create_all, get_session
    with app.app_context():
        create_all()
        db = get_session()
        try:
            site_a = str(uuid.uuid4())
            site_b = str(uuid.uuid4())
            dep_a1 = str(uuid.uuid4())
            dep_b1 = str(uuid.uuid4())
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_a, "n": "Site A"})
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_b, "n": "Site B"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',8,0)"), {"i": dep_a1, "s": site_a, "n": "Avd A1"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',5,0)"), {"i": dep_b1, "s": site_b, "n": "Avd B1"})
            db.commit()
            return site_a, site_b, dep_a1, dep_b1
        finally:
            db.close()


def test_portal_customer_admin_ignores_query_site_id(client_admin):
    app = client_admin.application
    year, week = 2026, 8
    site_a, site_b, dep_a1, dep_b1 = _seed_two_sites(app)
    # Bind session to site A as customer admin
    with client_admin.session_transaction() as s:
        s["site_id"] = site_a
        s["site_lock"] = False  # even when unlocked, must ignore query site
        s["role"] = "admin"
    # GET with query pointing to site B; should still render site A context/picker
    r = client_admin.get(f"/ui/portal/week?site_id={site_b}&year={year}&week={week}", headers=ADMIN_HEADERS)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    # Department picker should list only Site A department(s)
    assert "Avd A1" in html
    assert "Avd B1" not in html
    # Data attribute on container should reflect Site A
    assert f'data-site-id="{site_a}"' in html
