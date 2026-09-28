import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo


def _seed_site_and_departments(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL);
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS departments (
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT NOT NULL,
            resident_count_mode TEXT NOT NULL,
            resident_count_fixed INTEGER NOT NULL DEFAULT 0
        );
    """))
    site_id = "site-1"
    db.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES(:i,:n)"), {"i": site_id, "n": "Testplats"})
    db.execute(text("INSERT OR IGNORE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed) VALUES(:i,:s,:n,'manual',:f)"), {"i": "dep-A", "s": site_id, "n": "Avd A", "f": 10})
    db.execute(text("INSERT OR IGNORE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed) VALUES(:i,:s,:n,'manual',:f)"), {"i": "dep-B", "s": site_id, "n": "Avd B", "f": 8})
    return site_id


def _seed_diet_types(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS dietary_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id TEXT NULL,
            name TEXT NOT NULL,
            default_select INTEGER NOT NULL DEFAULT 0
        );
    """))
    # Ensure site_id column exists for strict isolation
    # (No-op: table definition above includes site_id)


def _seed_diet_defaults(db):
    db.execute(text(
        """
        CREATE TABLE IF NOT EXISTS department_diet_defaults (
            department_id TEXT NOT NULL,
            diet_type_id TEXT NOT NULL,
            default_count INTEGER NOT NULL DEFAULT 0,
            always_mark INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (department_id, diet_type_id)
        )
        """
    ))
    # For Avd A: 1 Gluten + 1 Laktos defaults (names align with marks)
    db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES('dep-A','Gluten',1)"))
    db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES('dep-A','Laktos',1)"))


def _seed_weekview(db, year: int, week: int):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS weekview_registrations (
          tenant_id TEXT NOT NULL,
          department_id TEXT NOT NULL,
          year INTEGER NOT NULL,
          week INTEGER NOT NULL,
          day_of_week INTEGER NOT NULL,
          meal TEXT NOT NULL,
          diet_type TEXT NOT NULL,
          marked INTEGER NOT NULL DEFAULT 0,
          UNIQUE (tenant_id, department_id, year, week, day_of_week, meal, diet_type)
        );
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS weekview_versions (
          tenant_id TEXT NOT NULL,
          department_id TEXT NOT NULL,
          year INTEGER NOT NULL,
          week INTEGER NOT NULL,
          version INTEGER NOT NULL DEFAULT 0,
          UNIQUE (tenant_id, department_id, year, week)
        );
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS weekview_residents_count (
            tenant_id TEXT NOT NULL,
            department_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            week INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            meal TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            UNIQUE (tenant_id, department_id, year, week, day_of_week, meal)
        );
    """))
    for dep in ("dep-A", "dep-B"):
        db.execute(text("INSERT OR IGNORE INTO weekview_versions(tenant_id,department_id,year,week,version) VALUES('1',:d,:y,:w,0)"), {"d": dep, "y": year, "w": week})
    for dow in range(1, 8):
        for meal in ("lunch", "dinner"):
            db.execute(text("INSERT OR REPLACE INTO weekview_residents_count(tenant_id,department_id,year,week,day_of_week,meal,count) VALUES('1','dep-A',:y,:w,:d,:m,:c)"), {"y": year, "w": week, "d": dow, "m": meal, "c": 10})
            count_b = 6 if (dow == 3 and meal == "lunch") else 8
            db.execute(text("INSERT OR REPLACE INTO weekview_residents_count(tenant_id,department_id,year,week,day_of_week,meal,count) VALUES('1','dep-B',:y,:w,:d,:m,:c)"), {"y": year, "w": week, "d": dow, "m": meal, "c": count_b})
    # Specials for Avd A
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1','dep-A',:y,:w,1,'lunch','Gluten',1)"), {"y": year, "w": week})
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1','dep-A',:y,:w,1,'lunch','Laktos',1)"), {"y": year, "w": week})
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1','dep-A',:y,:w,1,'lunch','Normalkost',1)"), {"y": year, "w": week})
    db.execute(text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1','dep-A',:y,:w,2,'lunch','Gluten',1)"), {"y": year, "w": week})
    # Avd B Sunday dinner 0 residents
    db.execute(text("UPDATE weekview_residents_count SET count=0 WHERE tenant_id='1' AND department_id='dep-B' AND year=:y AND week=:w AND day_of_week=7 AND meal='dinner'"), {"y": year, "w": week})


def test_seeded_weekly_diets_report(client):
    year, week = 2025, 10
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s["site_id"] = "site-1"
    from core.db import get_session
    db = get_session()
    try:
        _seed_site_and_departments(db)
        _seed_diet_types(db)
        _seed_weekview(db, year, week)
        _seed_diet_defaults(db)
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=ALL&view=day")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Veckorapport" in html
    assert "Filter" in html
    assert "Sammanställning" in html
    assert "Alla avdelningar" in html
    assert "Normal" in html
    assert "Special" in html
    assert "<details" in html
    assert "Avd A" in html and "Avd B" in html
    assert "Lunch" in html
    assert "Kväll" in html

    resp2 = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=ALL&view=week")
    assert resp2.status_code == 200
    html2 = resp2.get_data(as_text=True)
    assert "Avd A" in html2
    assert "Täckning:" not in html2

    resp3 = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=dep-A&view=week")
    assert resp3.status_code == 200
    html3 = resp3.get_data(as_text=True)
    assert "Avd A" in html3
    assert "admin-report-week__context" in html3
    assert "Vecka 10, 2025" in html3
    assert "Vecka 10, 2025 · Avd A" in html3
    assert "Normal" in html3
    assert "Special" in html3

    resp4 = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=dep-B&view=day")
    assert resp4.status_code == 200
    html4 = resp4.get_data(as_text=True)
    assert "Avd B" in html4


def test_admin_report_week_uses_cohort_truth_when_groups_exist(client):
    year, week = 2026, 37

    from core.db import get_session

    db = get_session()
    try:
        site_repo = SitesRepo()
        dept_repo = DepartmentsRepo()
        diet_repo = DietTypesRepo()
        group_repo = DepartmentRequirementGroupsRepo()
        completion_repo = DepartmentRequirementGroupCompletionRepo()

        site, _ = site_repo.create_site(name="Cohort Bridge Site", tenant_id=1)
        dept_a, _ = dept_repo.create_department(site_id=site["id"], name="Avdelning 11", resident_count_mode="fixed", resident_count_fixed=10)
        dept_b, _ = dept_repo.create_department(site_id=site["id"], name="Avdelning 13", resident_count_mode="fixed", resident_count_fixed=8)
        dept_c, _ = dept_repo.create_department(site_id=site["id"], name="Avdelning 16", resident_count_mode="fixed", resident_count_fixed=10)

        gluten = diet_repo.create(site_id=site["id"], name="Glutenfri", default_select=True, semantics="atomic")
        lactose = diet_repo.create(site_id=site["id"], name="Laktosfri", default_select=False, semantics="atomic")
        egg = diet_repo.create(site_id=site["id"], name="Äggfri", default_select=False, semantics="atomic")
        timbal = diet_repo.create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
        vegetarian = diet_repo.create(site_id=site["id"], name="Vegetarisk", default_select=False, semantics="atomic")

        # Legacy truth that must be ignored once registered requirement groups exist.
        dept_repo.upsert_department_diet_defaults(
            dept_a["id"],
            0,
            [{"diet_type_id": gluten, "default_count": 9}],
        )

        group_a = group_repo.create_group(dept_a["id"], 1, [gluten], label="Glutenfri", primary_requirement_id=gluten)
        group_a_incomplete = group_repo.create_group(dept_a["id"], 2, [lactose, egg], label="Laktosfri + Äggfri", primary_requirement_id=lactose)
        group_b = group_repo.create_group(dept_b["id"], 1, [timbal, lactose], label="Timbal + Laktosfri", primary_requirement_id=timbal)
        group_c1 = group_repo.create_group(dept_c["id"], 3, [gluten], label="Glutenfri", primary_requirement_id=gluten)
        group_c2 = group_repo.create_group(dept_c["id"], 1, [vegetarian, egg], label="Vegetarisk + Äggfri", primary_requirement_id=vegetarian)

        completion_repo.set_marked(dept_a["id"], group_a["id"], "2026-09-08", "lunch", True)
        completion_repo.set_marked(dept_a["id"], group_a_incomplete["id"], "2026-09-08", "lunch", False)
        completion_repo.set_marked(dept_b["id"], group_b["id"], "2026-09-08", "lunch", True)
        completion_repo.set_marked(dept_c["id"], group_c1["id"], "2026-09-08", "lunch", True)
        completion_repo.set_marked(dept_c["id"], group_c2["id"], "2026-09-08", "lunch", True)
        db.commit()
    finally:
        db.close()

    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s["site_id"] = site["id"]

    resp = client.get(f"/ui/admin/report/week?year={year}&week={week}&department_id=ALL&view=day")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "Avdelning 11" in html
    assert "Lunch: Normal 69 · Special 1" in html
    assert "Avdelning 13" in html
    assert "Lunch: Normal 55 · Special 1" in html
    assert "Avdelning 16" in html
    assert "Lunch: Normal 66 · Special 4" in html
