import uuid
from datetime import date

import pytest
from core.models import User
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo


ETAG_RE = __import__("re").compile(r'^W/"weekview:dept:.*:year:\d{4}:week:\d{1,2}:v\d+"$')


def _h():
    return {}


def _bind_test_admin_to_site(client, site_id, role="admin"):
    from core.db import get_session

    with client.application.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text(
                    "DELETE FROM kitchen_user_sites "
                    "WHERE user_id NOT IN (SELECT id FROM users)"
                )
            )
            user = User(
                tenant_id=1,
                username=f"phase2e-{uuid.uuid4().hex}@example.test",
                email=f"phase2e-{uuid.uuid4().hex}@example.test",
                password_hash="fixture-only",
                role=role,
                is_active=True,
                auth_version=1,
                must_change_password=False,
            )
            db.add(user)
            db.flush()
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:user_id, 1, :site_id)"
                ),
                {"user_id": user.id, "site_id": site_id},
            )
            db.commit()
            user_id = user.id
        finally:
            db.close()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = role
        sess["tenant_id"] = 1
        sess["auth_version"] = 1
        sess["site_id"] = site_id
        sess["tenant_id"] = 1


def _canonical_diet_id(site_id: str, name: str, *, default_select: bool) -> int:
    row = next(row for row in DietTypesRepo().list_all(site_id=site_id) if row["name"] == name)
    assert row["semantics"] == "atomic"
    assert row["requirement_key"]
    if bool(row["default_select"]) != default_select:
        DietTypesRepo().update(int(row["id"]), default_select=default_select)
        row = next(row for row in DietTypesRepo().list_all(site_id=site_id) if row["name"] == name)
    assert bool(row["default_select"]) is default_select
    return int(row["id"])


@pytest.fixture
def enable_weekview(client_admin):
    with client_admin.session_transaction() as sess:
        default_site_id = sess["site_id"]
    _bind_test_admin_to_site(client_admin, default_site_id)
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_h(),
    )
    assert resp.status_code == 200


@pytest.fixture
def client_editor(app_session):
    client = app_session.test_client()
    client.environ_base = {}
    return client


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_report_aggregation_api_and_ui(client_admin, client_editor):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_a = str(uuid.uuid4())
    dep_b = str(uuid.uuid4())
    year, week = 2025, 48

    import os
    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            # Site and departments
            db.execute(text("INSERT INTO sites(id, name, tenant_id, version) VALUES(:i,:n,1,0)"), {"i": site_id, "n": "ReportSite"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_a, "s": site_id, "n": "Avd A"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_b, "s": site_id, "n": "Avd B"})
            db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
            db.commit()
        finally:
            db.close()
        diet_repo = DietTypesRepo()
        diet_ids = {
            name: diet_repo.create(
                site_id=site_id,
                tenant_id=1,
                name=name,
                semantics="atomic",
            )
            for name in ("Gluten", "Laktos", "Timbal")
        }
        db = get_session()
        try:
            for department_id, name, count in (
                (dep_a, "Gluten", 2),
                (dep_a, "Laktos", 1),
                (dep_b, "Timbal", 3),
            ):
                db.execute(
                    text(
                        "INSERT INTO department_diet_defaults"
                        "(department_id, diet_type_id, default_count) VALUES(:d,:t,:c)"
                    ),
                    {
                        "d": department_id,
                        "t": str(diet_ids[name]),
                        "c": count,
                    },
                )
            db.commit()
        finally:
            db.close()
    _bind_test_admin_to_site(client_admin, site_id)
    _bind_test_admin_to_site(client_editor, site_id, role="editor")

    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_h(),
    )
    assert resp.status_code == 200

    # Materialize baseline weekviews and set data
    # A: residents lunch Mon=10, Tue=8; dinner Tue=5; mark Gluten Mon lunch and Wed lunch; Laktos Tue dinner
    base_a = f"/api/weekview?year={year}&week={week}&department_id={dep_a}"
    r0a = client_admin.get(base_a, headers=_h())
    assert r0a.status_code == 200 and ETAG_RE.match(r0a.headers.get("ETag") or "")
    etag_a = r0a.headers.get("ETag")

    def _iso(y, w, dow):
        return date.fromisocalendar(y, w, dow).isoformat()

    # Set residents & marks for A
    client_admin.patch("/api/weekview/residents", headers={"If-Match": etag_a}, json={
        "tenant_id": 1,
        "department_id": dep_a,
        "year": year,
        "week": week,
        "items": [
            {"day_of_week": 1, "meal": "lunch", "count": 10},
            {"day_of_week": 2, "meal": "lunch", "count": 8},
            {"day_of_week": 2, "meal": "dinner", "count": 5},
        ],
    })
    # Refresh ETag after residents update before marking diets
    r_a_after_res = client_admin.get(base_a, headers=_h())
    assert r_a_after_res.status_code == 200 and ETAG_RE.match(r_a_after_res.headers.get("ETag") or "")
    etag_a = r_a_after_res.headers.get("ETag")
    editor_mark_a1 = client_editor.patch("/api/weekview/specialdiets/mark", headers={"If-Match": etag_a}, json={
        "site_id": site_id,
        "department_id": dep_a,
        "local_date": _iso(year, week, 1),
        "meal": "lunch",
        "diet_type_id": str(diet_ids["Gluten"]),
        "marked": True,
    })
    assert editor_mark_a1.status_code == 200
    # Fetch new etag and set next mark
    r1a = client_admin.get(base_a, headers=_h())
    etag_a2 = r1a.headers.get("ETag") or etag_a
    editor_mark_a2 = client_editor.patch("/api/weekview/specialdiets/mark", headers={"If-Match": etag_a2}, json={
        "site_id": site_id,
        "department_id": dep_a,
        "local_date": _iso(year, week, 3),
        "meal": "lunch",
        "diet_type_id": str(diet_ids["Gluten"]),
        "marked": True,
    })
    assert editor_mark_a2.status_code == 200
    r2a = client_admin.get(base_a, headers=_h())
    etag_a3 = r2a.headers.get("ETag") or etag_a2
    editor_mark_a3 = client_editor.patch("/api/weekview/specialdiets/mark", headers={"If-Match": etag_a3}, json={
        "site_id": site_id,
        "department_id": dep_a,
        "local_date": _iso(year, week, 2),
        "meal": "dinner",
        "diet_type_id": str(diet_ids["Laktos"]),
        "marked": True,
    })
    assert editor_mark_a3.status_code == 200

    # B: residents dinner Thu=7; mark Timbal Thu dinner
    base_b = f"/api/weekview?year={year}&week={week}&department_id={dep_b}"
    r0b = client_admin.get(base_b, headers=_h())
    assert r0b.status_code == 200 and ETAG_RE.match(r0b.headers.get("ETag") or "")
    etag_b = r0b.headers.get("ETag")
    client_admin.patch("/api/weekview/residents", headers={"If-Match": etag_b}, json={
        "tenant_id": 1,
        "department_id": dep_b,
        "year": year,
        "week": week,
        "items": [
            {"day_of_week": 4, "meal": "dinner", "count": 7},
        ],
    })
    # Refresh ETag after residents update before marking diets for B
    r_b_after_res = client_admin.get(base_b, headers=_h())
    assert r_b_after_res.status_code == 200 and ETAG_RE.match(r_b_after_res.headers.get("ETag") or "")
    etag_b = r_b_after_res.headers.get("ETag")
    editor_mark_b = client_editor.patch("/api/weekview/specialdiets/mark", headers={"If-Match": etag_b}, json={
        "site_id": site_id,
        "department_id": dep_b,
        "local_date": _iso(year, week, 4),
        "meal": "dinner",
        "diet_type_id": str(diet_ids["Timbal"]),
        "marked": True,
    })
    assert editor_mark_b.status_code == 200

    # API single department (A)
    r_api_a = client_admin.get(f"/api/reports/weekview?site_id={site_id}&year={year}&week={week}&department_id={dep_a}", headers=_h())
    assert r_api_a.status_code == 200
    data_a = r_api_a.get_json()
    dept_a = data_a["departments"][0]
    assert dept_a["department_id"] == dep_a
    lunch = dept_a["meals"]["lunch"]
    dinner = dept_a["meals"]["dinner"]
    assert lunch["residents_total"] == 18
    assert lunch["debiterbar_specialkost_count"] == 4  # Gluten default 2 marked twice (Mon+Wed lunch)
    assert dinner["residents_total"] == 5
    assert dinner["debiterbar_specialkost_count"] == 1  # Laktos default 1 marked once (Tue dinner)
    assert dinner["normal_diet_count"] == 4  # 5 - 1

    # API all departments
    r_api_all = client_admin.get(f"/api/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=_h())
    assert r_api_all.status_code == 200
    data_all = r_api_all.get_json()
    assert {dep_a, dep_b}.issubset({d["department_id"] for d in data_all["departments"]})
    dep_b_meals = [d for d in data_all["departments"] if d["department_id"] == dep_b][0]["meals"]
    assert dep_b_meals["dinner"]["residents_total"] == 7
    assert dep_b_meals["dinner"]["debiterbar_specialkost_count"] == 3  # Timbal default 3 marked once

    # UI template renders
    r_ui = client_admin.get(f"/ui/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=_h())
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    assert "Statistik – vecka" in html
    assert "Avd A" in html and "Avd B" in html
    assert "Lunch" in html and "Kvällsmat" in html
    assert "Ingen specialkost" not in html  # we have some


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_report_default_select_marked_specialkost_comes_from_weekview_payload(client_admin):
    app = client_admin.application
    year, week = 2025, 49

    from core.admin_repo import DepartmentsRepo, DietTypesRepo, DepartmentDietOverridesRepo, SitesRepo

    with app.app_context():
        site, _ = SitesRepo().create_site(name=f"ReportSite-{uuid.uuid4().hex[:8]}", tenant_id=1)
        dept, _ = DepartmentsRepo().create_department(
            site_id=site["id"],
            name=f"Avd C-{uuid.uuid4().hex[:8]}",
            resident_count_mode="fixed",
            resident_count_fixed=10,
        )
        diet_id = _canonical_diet_id(site["id"], "Glutenfri", default_select=True)
        DepartmentsRepo().upsert_department_diet_defaults(
            dept["id"],
            0,
            [{"diet_type_id": diet_id, "default_count": 2}],
        )
        DepartmentDietOverridesRepo().replace_for_department_diet(
            dept["id"],
            diet_id,
            [
                {"day": 1, "meal": "lunch", "count": 2},
                {"day": 1, "meal": "dinner", "count": 0},
                {"day": 2, "meal": "lunch", "count": 0},
                {"day": 2, "meal": "dinner", "count": 0},
                {"day": 3, "meal": "lunch", "count": 0},
                {"day": 3, "meal": "dinner", "count": 0},
                {"day": 4, "meal": "lunch", "count": 0},
                {"day": 4, "meal": "dinner", "count": 0},
                {"day": 5, "meal": "lunch", "count": 0},
                {"day": 5, "meal": "dinner", "count": 0},
                {"day": 6, "meal": "lunch", "count": 0},
                {"day": 6, "meal": "dinner", "count": 0},
                {"day": 7, "meal": "lunch", "count": 0},
                {"day": 7, "meal": "dinner", "count": 0},
            ],
        )
    _bind_test_admin_to_site(client_admin, site["id"])

    base = f"/api/weekview?year={year}&week={week}&department_id={dept['id']}"
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["tenant_id"] = 1
    r0 = client_admin.get(base, headers=_h())
    assert r0.status_code == 200
    etag = r0.headers.get("ETag")
    assert etag

    r_res = client_admin.patch(
        "/api/weekview/residents",
        headers={"If-Match": etag},
        json={
            "tenant_id": 1,
            "site_id": site["id"],
            "department_id": dept["id"],
            "year": year,
            "week": week,
            "items": [{"day_of_week": 1, "meal": "lunch", "count": 10}],
        },
    )
    assert r_res.status_code in (200, 201)

    r_api = client_admin.get(f"/api/reports/weekview?site_id={site['id']}&year={year}&week={week}&department_id={dept['id']}", headers=_h())
    assert r_api.status_code == 200
    data = r_api.get_json()
    dept_vm = data["departments"][0]
    lunch = dept_vm["meals"]["lunch"]
    monday = dept_vm["days"][0]

    assert lunch["residents_total"] == 70
    assert lunch["debiterbar_specialkost_count"] == 2
    assert lunch["normal_diet_count"] == 68
    assert monday["lunch_debiterbar"] == 2


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_report_cohort_bridge_uses_group_completions_and_ignores_legacy_defaults(client_admin):
    app = client_admin.application
    year, week = 2026, 37

    with app.app_context():
        site, _ = SitesRepo().create_site(name=f"Cohort Bridge Site-{uuid.uuid4().hex[:8]}", tenant_id=1)
        dept_a, _ = DepartmentsRepo().create_department(site_id=site["id"], name="Avdelning 11", resident_count_mode="fixed", resident_count_fixed=10)
        dept_b, _ = DepartmentsRepo().create_department(site_id=site["id"], name="Avdelning 13", resident_count_mode="fixed", resident_count_fixed=8)
        dept_c, _ = DepartmentsRepo().create_department(site_id=site["id"], name="Avdelning 16", resident_count_mode="fixed", resident_count_fixed=10)

        gluten = _canonical_diet_id(site["id"], "Glutenfri", default_select=True)
        lactose = _canonical_diet_id(site["id"], "Laktosfri", default_select=False)
        egg = _canonical_diet_id(site["id"], "Äggfri", default_select=False)
        timbal = _canonical_diet_id(site["id"], "Timbal", default_select=False)
        vegetarian = _canonical_diet_id(site["id"], "Vegetarisk", default_select=False)

        # Legacy data that would overcount if the report did not switch to cohort truth.
        DepartmentsRepo().upsert_department_diet_defaults(
            dept_a["id"],
            0,
            [{"diet_type_id": gluten, "default_count": 9}],
        )
        groups = DepartmentRequirementGroupsRepo()
        completions = DepartmentRequirementGroupCompletionRepo()

        group_a_done = groups.create_group(dept_a["id"], 1, [gluten], label="Glutenfri", primary_requirement_id=gluten)
        group_a_not_done = groups.create_group(dept_a["id"], 2, [lactose, egg], label="Laktosfri + Äggfri", primary_requirement_id=lactose)
        group_b_done = groups.create_group(dept_b["id"], 1, [timbal, lactose], label="Timbal + Laktosfri", primary_requirement_id=timbal)
        group_c_gluten = groups.create_group(dept_c["id"], 3, [gluten], label="Glutenfri", primary_requirement_id=gluten)
        group_c_veg = groups.create_group(dept_c["id"], 1, [vegetarian, egg], label="Vegetarisk + Äggfri", primary_requirement_id=vegetarian)

        completions.set_marked(dept_a["id"], group_a_done["id"], "2026-09-08", "lunch", True)
        completions.set_marked(dept_a["id"], group_a_not_done["id"], "2026-09-08", "lunch", False)
        completions.set_marked(dept_b["id"], group_b_done["id"], "2026-09-08", "lunch", True)
        completions.set_marked(dept_c["id"], group_c_gluten["id"], "2026-09-08", "lunch", True)
        completions.set_marked(dept_c["id"], group_c_veg["id"], "2026-09-08", "lunch", True)

    _bind_test_admin_to_site(client_admin, site["id"])

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
        sess["tenant_id"] = 1

    r_api = client_admin.get(f"/api/reports/weekview?site_id={site['id']}&year={year}&week={week}", headers=_h())
    assert r_api.status_code == 200
    data = r_api.get_json()
    deps = {dep["department_name"]: dep for dep in data["departments"]}

    assert deps["Avdelning 11"]["meals"]["lunch"]["residents_total"] == 70
    assert deps["Avdelning 11"]["meals"]["lunch"]["debiterbar_specialkost_count"] == 1
    assert deps["Avdelning 11"]["meals"]["lunch"]["normal_diet_count"] == 69
    assert deps["Avdelning 11"]["days"][1]["lunch_debiterbar"] == 1

    assert deps["Avdelning 13"]["meals"]["lunch"]["residents_total"] == 56
    assert deps["Avdelning 13"]["meals"]["lunch"]["debiterbar_specialkost_count"] == 1
    assert deps["Avdelning 13"]["meals"]["lunch"]["normal_diet_count"] == 55
    assert deps["Avdelning 13"]["days"][1]["lunch_debiterbar"] == 1

    assert deps["Avdelning 16"]["meals"]["lunch"]["residents_total"] == 70
    assert deps["Avdelning 16"]["meals"]["lunch"]["debiterbar_specialkost_count"] == 4
    assert deps["Avdelning 16"]["meals"]["lunch"]["normal_diet_count"] == 66
    assert deps["Avdelning 16"]["days"][1]["lunch_debiterbar"] == 4
