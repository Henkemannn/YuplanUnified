import uuid


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_week_ui_department_filter_groundwork(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_a = str(uuid.uuid4())
    dep_b = str(uuid.uuid4())
    year, week = 2025, 49

    from core.db import create_all, get_session
    from sqlalchemy import text
    import os
    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "SiteDF"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_a, "s": site_id, "n": "AvdA"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_b, "s": site_id, "n": "AvdB"})
            db.commit()
        finally:
            db.close()
        reg = getattr(app, "feature_registry", None)
        if reg and not reg.has("ff.planera.enabled"):
            reg.add("ff.planera.enabled")

    # Without filter
    r_all = client_admin.get(f"/ui/planera/week?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r_all.status_code == 200
    html_all = r_all.get_data(as_text=True)
    assert "SiteDF" in html_all

    # With department filter (groundwork: just ensure 200 and department id present marker in HTML context if exposed)
    r_one = client_admin.get(f"/ui/planera/week?site_id={site_id}&year={year}&week={week}&department_id={dep_a}", headers=_h("admin"))
    assert r_one.status_code == 200
    html_one = r_one.get_data(as_text=True)
    # Template currently does not render department names; groundwork only asserts site still present
    assert "SiteDF" in html_one
