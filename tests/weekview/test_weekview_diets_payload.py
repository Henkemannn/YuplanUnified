import uuid
import pytest

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
            # Seed department diet defaults
            db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
            db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:t,:c) ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count"), {"d": dep_id, "t": "gluten", "c": 2})
            db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:t,:c) ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count"), {"d": dep_id, "t": "laktos", "c": 1})
            db.commit()
        finally:
            db.close()

    # Materialize base payload
    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    # Align session site context
    client_admin.post(
        "/ui/select-site",
        data={"site_id": site_id, "next": "/"},
        headers=_h("admin"),
    )
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
            "diet_type_id": "gluten",
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
    gluten = next((r for r in lunch_rows if r["diet_type_id"] == "gluten"), None)
    laktos = next((r for r in lunch_rows if r["diet_type_id"] == "laktos"), None)
    assert gluten and gluten["resident_count"] == 2 and gluten["marked"] is True
    assert laktos and laktos["resident_count"] == 1 and laktos["marked"] is False
