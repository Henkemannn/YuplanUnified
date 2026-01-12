import uuid
from sqlalchemy import text

HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_departments():
    from core.db import get_session
    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep1 = str(uuid.uuid4())
        dep2 = str(uuid.uuid4())
        db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,'Testgården',0)"), {"i": site_id})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,'D1','fixed',5,0)"), {"i": dep1, "s": site_id})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,'D2','fixed',6,0)"), {"i": dep2, "s": site_id})
        db.commit()
        return site_id, dep1, dep2
    finally:
        db.close()


def test_portal_uses_session_site_when_locked(client_admin):
    app = client_admin.application
    site_id, dep1, dep2 = _seed_site_and_departments()
    # Lock site in session and set to Testgården
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
        s["site_lock"] = True
        s["role"] = "admin"
    # Seed menu for this site so content appears
    from core.menu_repo import MenuRepo
    mr = MenuRepo()
    mr.upsert_menu_item(site_id, 2026, 8, day=2, meal="lunch", alt1_text="Pasta", alt2_text="Fisk", dessert="")
    # GET without site_id query param must still render picker and menu
    r = client_admin.get("/ui/portal/week?year=2026&week=8", headers=HEADERS_ADMIN)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Department picker uses effective site: both departments listed
    assert '<select id="portal-department-select"' in html
    assert 'D1' in html and 'D2' in html
    # Menu content appears (from MenuRepo overlay)
    assert 'Pasta' in html or 'Fisk' in html
