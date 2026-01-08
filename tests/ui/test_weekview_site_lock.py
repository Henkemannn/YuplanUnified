import uuid
from datetime import date as _date


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_weekview_site_lock_ignores_query_switch(app_session, client_admin):
    # Seed two sites in tenant
    from core.admin_repo import SitesRepo
    with app_session.app_context():
        site_a, _ = SitesRepo().create_site("Locked Site")
        site_b, _ = SitesRepo().create_site("Other Site")
    # Bind session to site_a with site_lock
    with client_admin.session_transaction() as s:
        s["site_id"] = site_a["id"]
        s["site_lock"] = True
        s["role"] = "admin"
        s["tenant_id"] = 1
    # Compute current ISO year/week
    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]
    # Attempt to switch via querystring to site_b
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_b['id']}&year={year}&week={week}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Must render locked site content and hide switcher UI
    assert "Locked Site" in html
    assert "Byt site" not in html
    assert "Other Site" not in html
