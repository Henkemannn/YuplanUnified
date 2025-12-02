import uuid


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_week_csv_export_and_304(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 50

    from core.db import create_all, get_session
    from sqlalchemy import text
    import os
    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            # Seed site + department
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "CSVSite"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_id, "s": site_id, "n": "AvdCSV"})
            # Seed diet defaults (will appear as potential diets, though not special unless marked)
            db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults(department_id TEXT, diet_type_id TEXT, default_count INTEGER, PRIMARY KEY(department_id,diet_type_id))"))
            db.execute(text("INSERT INTO department_diet_defaults(department_id,diet_type_id,default_count) VALUES(:d,'Gluten',2)"), {"d": dep_id})
            # Mark Gluten diet for Monday lunch (day_of_week=1)
            db.execute(text("INSERT INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES(:tid,:dep,:yy,:ww,1,'lunch','Gluten',1)"), {"tid": 1, "dep": dep_id, "yy": year, "ww": week})
            # Residents count for Monday lunch
            db.execute(text("INSERT INTO weekview_residents_count(tenant_id,department_id,year,week,day_of_week,meal,count) VALUES(:tid,:dep,:yy,:ww,1,'lunch',10)"), {"tid": 1, "dep": dep_id, "yy": year, "ww": week})
            db.commit()
        finally:
            db.close()
        reg = getattr(app, "feature_registry", None)
        if reg:
            if not reg.has("ff.planera.enabled"):
                reg.add("ff.planera.enabled")
            reg.set("ff.planera.enabled", True)

    # Initial CSV fetch
    r1 = client_admin.get(f"/api/planera/week/csv?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r1.status_code == 200
    assert r1.headers.get("Content-Type", "").startswith("text/csv")
    etag = r1.headers.get("ETag")
    body = r1.get_data(as_text=True)
    lines = [l for l in body.splitlines() if l.strip()]
    assert lines[0].startswith("date,weekday,meal,department,residents_total,normal,special_diets")
    # Expect a line with Gluten diet (special_diets column includes Gluten:2)
    assert any("Gluten:2" in l for l in lines[1:])

    # Conditional GET with ETag
    r2 = client_admin.get(f"/api/planera/week/csv?site_id={site_id}&year={year}&week={week}", headers={**_h("admin"), "If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.get_data(as_text=True) == ""

