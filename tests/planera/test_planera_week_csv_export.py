import uuid

from tests._auth_site_helpers import login_bound_user


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
            db.execute(text("INSERT INTO sites(id, name, tenant_id, version) VALUES(:i,:n,1,0)"), {"i": site_id, "n": "CSVSite"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_id, "s": site_id, "n": "AvdCSV"})
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS weekview_registrations ("
                    "tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, "
                    "day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, "
                    "UNIQUE(tenant_id, department_id, year, week, day_of_week, meal, diet_type))"
                )
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS weekview_residents_count ("
                    "tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, "
                    "day_of_week INTEGER, meal TEXT, count INTEGER)"
                )
            )
            db.commit()
        finally:
            db.close()
        from core.admin_repo import DepartmentsRepo, DietTypesRepo

        diet_id = DietTypesRepo().create(
            site_id=site_id,
            tenant_id=1,
            name="Gluten",
            semantics="atomic",
        )
        DepartmentsRepo().upsert_department_diet_defaults(
            dep_id,
            0,
            [{"diet_type_id": str(diet_id), "default_count": 2}],
        )
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO weekview_registrations"
                    "(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) "
                    "VALUES(:tid,:dep,:yy,:ww,1,'lunch',:diet,1)"
                ),
                {"tid": 1, "dep": dep_id, "yy": year, "ww": week, "diet": str(diet_id)},
            )
            db.execute(
                text(
                    "INSERT INTO weekview_residents_count"
                    "(tenant_id,department_id,year,week,day_of_week,meal,count) "
                    "VALUES(:tid,:dep,:yy,:ww,1,'lunch',10)"
                ),
                {"tid": 1, "dep": dep_id, "yy": year, "ww": week},
            )
            db.commit()
        finally:
            db.close()
        reg = getattr(app, "feature_registry", None)
        if reg:
            if not reg.has("ff.planera.enabled"):
                reg.add("ff.planera.enabled")
            reg.set("ff.planera.enabled", True)

    login_bound_user(client_admin, site_id=site_id, role="admin")

    # Initial CSV fetch
    r1 = client_admin.get(f"/api/planera/week/csv?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r1.status_code == 200
    assert r1.headers.get("Content-Type", "").startswith("text/csv")
    etag = r1.headers.get("ETag")
    body = r1.get_data(as_text=True)
    lines = [line for line in body.splitlines() if line.strip()]
    assert lines[0].startswith("date,weekday,meal,department,residents_total,normal,special_diets")
    # Expect a line with Gluten diet (special_diets column includes Gluten:2)
    assert any("Gluten:2" in line for line in lines[1:])

    # Conditional GET with ETag
    r2 = client_admin.get(f"/api/planera/week/csv?site_id={site_id}&year={year}&week={week}", headers={**_h("admin"), "If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.get_data(as_text=True) == ""

