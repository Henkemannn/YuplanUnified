import pytest
from sqlalchemy import text


def test_diet_types_isolation_between_sites(client):
    # Seed two sites and one diet type on site A
    from core.admin_repo import DietTypesRepo
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
        db.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES('A','Site A')"))
        db.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES('B','Site B')"))
        db.commit()
    finally:
        db.close()

    # Create diet type for site A only
    DietTypesRepo().create(site_id='A', name='Glutenfri-A', default_select=False)

    # View list on site A
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s["site_id"] = "A"
    resp_a = client.get("/ui/admin/specialkost")
    assert resp_a.status_code == 200
    html_a = resp_a.get_data(as_text=True)
    assert "Glutenfri-A" in html_a

    # Switch to site B and ensure isolation
    with client.session_transaction() as s:
        s["site_id"] = "B"
    resp_b = client.get("/ui/admin/specialkost")
    assert resp_b.status_code == 200
    html_b = resp_b.get_data(as_text=True)
    assert "Glutenfri-A" not in html_b


def test_weekly_report_requires_site_selection_when_missing(client):
    # No site_id in session should trigger redirect to select-site
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s.pop("site_id", None)
    resp = client.get("/ui/admin/report/week?year=2025&week=10&department_id=ALL&view=day")
    # Should redirect to select-site
    assert resp.status_code in (301, 302)
    loc = resp.headers.get("Location", "")
    assert "/ui/select-site" in loc
