from datetime import date as _date
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_normals(site_id: str):
    from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
    srepo = SitesRepo(); srepo.create_site("Plan Site")
    drepo = DepartmentsRepo()
    depA, _ = drepo.create_department(site_id, "Avd A", "fixed", 12)
    depB, _ = drepo.create_department(site_id, "Avd B", "fixed", 10)
    depC, _ = drepo.create_department(site_id, "Avd C", "fixed", 11)
    trepo = DietTypesRepo()
    dt_laktos = trepo.create(site_id=site_id, name="Laktos", default_select=False)
    # Defaults per dept for selected diet
    vA = drepo.get_version(depA["id"]) or 0
    vB = drepo.get_version(depB["id"]) or 0
    vC = drepo.get_version(depC["id"]) or 0
    drepo.upsert_department_diet_defaults(depA["id"], vA, [{"diet_type_id": str(dt_laktos), "default_count": 3}])
    drepo.upsert_department_diet_defaults(depB["id"], vB, [{"diet_type_id": str(dt_laktos), "default_count": 2}])
    drepo.upsert_department_diet_defaults(depC["id"], vC, [{"diet_type_id": str(dt_laktos), "default_count": 4}])
    return {"deps": (depA, depB, depC), "diet_id": dt_laktos}


def _seed_alt2_flag(site_id: str, department_id: str, year: int, week: int, dow: int):
    # Insert direct into alt2 flags table used by weekview enrichment
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
                site_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 0,
                PRIMARY KEY (site_id, department_id, year, week, day_of_week)
            )
        """))
        db.execute(text(
            "INSERT OR REPLACE INTO weekview_alt2_flags (site_id, department_id, year, week, day_of_week, enabled) VALUES (:s,:d,:y,:w,:dow,1)"
        ), {"s": site_id, "d": department_id, "y": year, "w": week, "dow": dow})
        db.commit()
    finally:
        db.close()


def test_normalkost_view_table_and_totals(app_session):
    client = app_session.test_client()
    site_id = "site-plan-1"
    seeded = _seed_normals(site_id)
    dt_id = seeded["diet_id"]
    (depA, depB, depC) = seeded["deps"]
    # Set Alt2 for Avd B on Monday (dow=1)
    today = _date.today()
    year = today.year; week = today.isocalendar()[1]
    _seed_alt2_flag(site_id, depB["id"], year, week, 1)

    # Request selected diets to compute normals
    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&day=0&meal=lunch&selected_diets={dt_id}&show_results=1",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")

    # Normals per dept: A=12-3=9 (Alt1), B=10-2=8 (Alt2), C=11-4=7 (Alt1)
    assert "Normalkost" in html
    assert "Avd A" in html and ">9<" in html
    assert "Avd B" in html and ">8<" in html
    assert "Avd C" in html and ">7<" in html
    # SUM = 24
    assert ">24<" in html
