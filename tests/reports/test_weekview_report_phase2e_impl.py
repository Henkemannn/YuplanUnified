import uuid
from datetime import date

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
def test_weekview_report_aggregation_api_and_ui(client_admin):
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
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "ReportSite"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_a, "s": site_id, "n": "Avd A"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_b, "s": site_id, "n": "Avd B"})
            # Diet defaults
            db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
            # Avd A: Gluten(2), Laktos(1)
            db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:t,:c) ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count"), {"d": dep_a, "t": "Gluten", "c": 2})
            db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:t,:c) ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count"), {"d": dep_a, "t": "Laktos", "c": 1})
            # Avd B: Timbal(3)
            db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:t,:c) ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count"), {"d": dep_b, "t": "Timbal", "c": 3})
            db.commit()
        finally:
            db.close()

    # Materialize baseline weekviews and set data
    # A: residents lunch Mon=10, Tue=8; dinner Tue=5; mark Gluten Mon lunch and Wed lunch; Laktos Tue dinner
    base_a = f"/api/weekview?year={year}&week={week}&department_id={dep_a}"
    r0a = client_admin.get(base_a, headers=_h("admin"))
    assert r0a.status_code == 200 and ETAG_RE.match(r0a.headers.get("ETag") or "")
    etag_a = r0a.headers.get("ETag")

    def _iso(y, w, dow):
        return date.fromisocalendar(y, w, dow).isoformat()

    # Set residents & marks for A
    client_admin.patch("/api/weekview/residents", headers={**_h("admin"), "If-Match": etag_a}, json={
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
    r_a_after_res = client_admin.get(base_a, headers=_h("admin"))
    assert r_a_after_res.status_code == 200 and ETAG_RE.match(r_a_after_res.headers.get("ETag") or "")
    etag_a = r_a_after_res.headers.get("ETag")
    client_admin.patch("/api/weekview/specialdiets/mark", headers={**_h("editor"), "If-Match": etag_a}, json={
        "site_id": site_id,
        "department_id": dep_a,
        "local_date": _iso(year, week, 1),
        "meal": "lunch",
        "diet_type_id": "Gluten",
        "marked": True,
    })
    # Fetch new etag and set next mark
    r1a = client_admin.get(base_a, headers=_h("admin"))
    etag_a2 = r1a.headers.get("ETag") or etag_a
    client_admin.patch("/api/weekview/specialdiets/mark", headers={**_h("editor"), "If-Match": etag_a2}, json={
        "site_id": site_id,
        "department_id": dep_a,
        "local_date": _iso(year, week, 3),
        "meal": "lunch",
        "diet_type_id": "Gluten",
        "marked": True,
    })
    r2a = client_admin.get(base_a, headers=_h("admin"))
    etag_a3 = r2a.headers.get("ETag") or etag_a2
    client_admin.patch("/api/weekview/specialdiets/mark", headers={**_h("editor"), "If-Match": etag_a3}, json={
        "site_id": site_id,
        "department_id": dep_a,
        "local_date": _iso(year, week, 2),
        "meal": "dinner",
        "diet_type_id": "Laktos",
        "marked": True,
    })

    # B: residents dinner Thu=7; mark Timbal Thu dinner
    base_b = f"/api/weekview?year={year}&week={week}&department_id={dep_b}"
    r0b = client_admin.get(base_b, headers=_h("admin"))
    assert r0b.status_code == 200 and ETAG_RE.match(r0b.headers.get("ETag") or "")
    etag_b = r0b.headers.get("ETag")
    client_admin.patch("/api/weekview/residents", headers={**_h("admin"), "If-Match": etag_b}, json={
        "tenant_id": 1,
        "department_id": dep_b,
        "year": year,
        "week": week,
        "items": [
            {"day_of_week": 4, "meal": "dinner", "count": 7},
        ],
    })
    # Refresh ETag after residents update before marking diets for B
    r_b_after_res = client_admin.get(base_b, headers=_h("admin"))
    assert r_b_after_res.status_code == 200 and ETAG_RE.match(r_b_after_res.headers.get("ETag") or "")
    etag_b = r_b_after_res.headers.get("ETag")
    client_admin.patch("/api/weekview/specialdiets/mark", headers={**_h("editor"), "If-Match": etag_b}, json={
        "site_id": site_id,
        "department_id": dep_b,
        "local_date": _iso(year, week, 4),
        "meal": "dinner",
        "diet_type_id": "Timbal",
        "marked": True,
    })

    # API single department (A)
    r_api_a = client_admin.get(f"/api/reports/weekview?site_id={site_id}&year={year}&week={week}&department_id={dep_a}", headers=_h("admin"))
    assert r_api_a.status_code == 200
    data_a = r_api_a.get_json()
    dept_a = data_a["departments"][0]
    assert dept_a["department_id"] == dep_a
    lunch = dept_a["meals"]["lunch"]
    dinner = dept_a["meals"]["dinner"]
    assert lunch["residents_total"] == 18
    assert any(d["diet_type_id"] == "Gluten" and d["count"] == 4 for d in lunch["special_diets"])  # 2+2
    assert dinner["residents_total"] == 5
    assert any(d["diet_type_id"] == "Laktos" and d["count"] == 1 for d in dinner["special_diets"])  # 1
    assert dinner["normal_diet_count"] == 4  # 5 - 1

    # API all departments
    r_api_all = client_admin.get(f"/api/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r_api_all.status_code == 200
    data_all = r_api_all.get_json()
    assert {dep_a, dep_b}.issubset({d["department_id"] for d in data_all["departments"]})
    dep_b_meals = [d for d in data_all["departments"] if d["department_id"] == dep_b][0]["meals"]
    assert dep_b_meals["dinner"]["residents_total"] == 7
    assert any(d["diet_type_id"] == "Timbal" and d["count"] == 3 for d in dep_b_meals["dinner"]["special_diets"])  # default 3 once

    # UI template renders
    r_ui = client_admin.get(f"/ui/reports/weekview?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    assert "Statistik – vecka" in html
    assert "Avd A" in html and "Avd B" in html
    assert "Lunch" in html and "Kvällsmat" in html
    assert "Ingen specialkost" not in html  # we have some
