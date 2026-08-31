import uuid
import pytest
from flask.testing import FlaskClient
from sqlalchemy import text
from core.admin_repo import DietTypesRepo, DepartmentsRepo, SitesRepo

ETAG_RE = __import__("re").compile(r'^W/"weekview:dept:.*:year:\d{4}:week:\d{1,2}:v\d+"$')


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_h("admin"),
    )
    assert resp.status_code == 200


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_diets_in_days_payload(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 48

    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Seed site + department
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Varberg"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_id, "s": site_id, "n": "Avd D"})
            db.commit()
        finally:
            db.close()

    diets_repo = DietTypesRepo()
    gluten_id = str(diets_repo.create(site_id=site_id, name="Glutenfri", default_select=False))
    laktos_id = str(diets_repo.create(site_id=site_id, name="Laktosfri", default_select=False))
    DepartmentsRepo().upsert_department_diet_defaults(
        dep_id,
        0,
        [
            {"diet_type_id": gluten_id, "default_count": 2},
            {"diet_type_id": laktos_id, "default_count": 1},
        ],
    )

    # Materialize base payload
    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    # Align session site context
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    r0 = client_admin.get(base, headers=_h("admin"))
    assert r0.status_code == 200 and ETAG_RE.match(r0.headers.get("ETag") or "")

    # Mark gluten on Monday lunch
    et = r0.headers.get("ETag")
    r_mark = client_admin.patch(
        "/api/weekview/specialdiets/mark",
        headers={**_h("editor"), "If-Match": et},
        json={
            "site_id": site_id,
            "department_id": dep_id,
            "local_date": "2025-11-24",  # ISO week 48, Monday
            "meal": "lunch",
            "diet_type_id": gluten_id,
            "marked": True,
        },
    )
    assert r_mark.status_code in (200, 201)

    # Fetch again and assert diets present with counts and marks
    r1 = client_admin.get(base, headers=_h("admin"))
    assert r1.status_code == 200
    j = r1.get_json()
    days = j["department_summaries"][0]["days"]
    mon = days[0]
    assert "diets" in mon and "lunch" in mon["diets"] and "dinner" in mon["diets"]
    lunch_rows = mon["diets"]["lunch"]
    # Gluten exists with resident_count=2 and marked=true; Laktos exists with resident_count=1 and marked=false
    gluten = next((r for r in lunch_rows if r["diet_type_id"] == gluten_id), None)
    laktos = next((r for r in lunch_rows if r["diet_type_id"] == laktos_id), None)
    assert gluten and gluten["resident_count"] == 2 and gluten["marked"] is True
    assert laktos and laktos["resident_count"] == 1 and laktos["marked"] is False


def _seed_marked_precedence_case(default_select: bool) -> tuple[str, str, str]:
    site, _ = SitesRepo().create_site(name=f"Test Site {uuid.uuid4().hex[:8]}", tenant_id=1)
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name=f"Avd A {uuid.uuid4().hex[:8]}",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    diet_id = str(DietTypesRepo().create(site_id=site["id"], name=f"Diet {uuid.uuid4().hex[:8]}", default_select=default_select))
    DepartmentsRepo().upsert_department_diet_defaults(
        dept["id"],
        0,
        [{"diet_type_id": diet_id, "default_count": 2}],
    )
    return site["id"], dept["id"], diet_id


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_diets_payload_default_select_true_without_explicit_row_is_marked(client_admin: FlaskClient):
    site_id, dep_id, diet_id = _seed_marked_precedence_case(default_select=True)
    year, week = 2025, 48

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    r = client_admin.get(f"/api/weekview?year={year}&week={week}&department_id={dep_id}", headers=_h("admin"))
    assert r.status_code == 200
    row = r.get_json()["department_summaries"][0]["days"][0]["diets"]["lunch"][0]
    assert row["diet_type_id"] == diet_id
    assert row["marked"] is True


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_diets_payload_default_select_true_explicit_false_still_marked(client_admin: FlaskClient):
    site_id, dep_id, diet_id = _seed_marked_precedence_case(default_select=True)
    year, week = 2025, 48

    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1',:d,:y,:w,1,'lunch',:t,0)"),
            {"d": dep_id, "y": year, "w": week, "t": diet_id},
        )
        db.commit()
    finally:
        db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    r = client_admin.get(f"/api/weekview?year={year}&week={week}&department_id={dep_id}", headers=_h("admin"))
    assert r.status_code == 200
    row = r.get_json()["department_summaries"][0]["days"][0]["diets"]["lunch"][0]
    assert row["diet_type_id"] == diet_id
    assert row["marked"] is True


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_diets_payload_explicit_true_is_marked(client_admin: FlaskClient):
    site_id, dep_id, diet_id = _seed_marked_precedence_case(default_select=False)
    year, week = 2025, 48

    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO weekview_registrations(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES('1',:d,:y,:w,1,'lunch',:t,1)"),
            {"d": dep_id, "y": year, "w": week, "t": diet_id},
        )
        db.commit()
    finally:
        db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    r = client_admin.get(f"/api/weekview?year={year}&week={week}&department_id={dep_id}", headers=_h("admin"))
    assert r.status_code == 200
    row = r.get_json()["department_summaries"][0]["days"][0]["diets"]["lunch"][0]
    assert row["diet_type_id"] == diet_id
    assert row["marked"] is True


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_diets_payload_default_select_false_without_explicit_row_is_unmarked(client_admin: FlaskClient):
    site_id, dep_id, diet_id = _seed_marked_precedence_case(default_select=False)
    year, week = 2025, 48

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    r = client_admin.get(f"/api/weekview?year={year}&week={week}&department_id={dep_id}", headers=_h("admin"))
    assert r.status_code == 200
    row = r.get_json()["department_summaries"][0]["days"][0]["diets"]["lunch"][0]
    assert row["diet_type_id"] == diet_id
    assert row["marked"] is False
