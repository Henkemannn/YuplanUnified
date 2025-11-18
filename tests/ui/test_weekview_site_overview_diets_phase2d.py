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
def test_weekview_site_overview_diets_phase2d(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_a = str(uuid.uuid4())
    dep_b = str(uuid.uuid4())
    year, week = 2025, 47

    import os
    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        # Enable lightweight SQLite bootstrap schema for tests
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            # Site and departments
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Varberg"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_a, "s": site_id, "n": "Avd A"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_b, "s": site_id, "n": "Avd B"})
            # Diet defaults for both departments: Gluten(2), Laktos(1)
            db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
            for dep in (dep_a, dep_b):
                db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:t,:c) ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count"), {"d": dep, "t": "gluten", "c": 2})
                db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:t,:c) ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count"), {"d": dep, "t": "laktos", "c": 1})
            db.commit()
        finally:
            db.close()

    # Materialize baseline + capture ETags for each department
    base_a = f"/api/weekview?year={year}&week={week}&department_id={dep_a}"
    r0a = client_admin.get(base_a, headers=_h("admin"))
    assert r0a.status_code == 200 and ETAG_RE.match(r0a.headers.get("ETag") or "")
    etag_a = r0a.headers.get("ETag")

    base_b = f"/api/weekview?year={year}&week={week}&department_id={dep_b}"
    r0b = client_admin.get(base_b, headers=_h("admin"))
    assert r0b.status_code == 200 and ETAG_RE.match(r0b.headers.get("ETag") or "")
    etag_b = r0b.headers.get("ETag")

    # Marks:
    # Dep A: Gluten marked on Mon lunch and Wed lunch => 2+2 = 4
    r_mark_a1 = client_admin.patch(
        "/api/weekview/specialdiets/mark",
        headers={**_h("editor"), "If-Match": etag_a},
        json={
            "site_id": site_id,
            "department_id": dep_a,
            "local_date": "2025-11-17",  # Week 47 Monday
            "meal": "lunch",
            "diet_type_id": "gluten",
            "marked": True,
        },
    )
    assert r_mark_a1.status_code in (200, 201)
    etag_a2 = r_mark_a1.headers.get("ETag") or etag_a

    r_mark_a2 = client_admin.patch(
        "/api/weekview/specialdiets/mark",
        headers={**_h("editor"), "If-Match": etag_a2},
        json={
            "site_id": site_id,
            "department_id": dep_a,
            "local_date": "2025-11-19",  # Week 47 Wednesday
            "meal": "lunch",
            "diet_type_id": "gluten",
            "marked": True,
        },
    )
    assert r_mark_a2.status_code in (200, 201)

    # Dep B: Laktos marked on Thu dinner => 1
    r_mark_b1 = client_admin.patch(
        "/api/weekview/specialdiets/mark",
        headers={**_h("editor"), "If-Match": etag_b},
        json={
            "site_id": site_id,
            "department_id": dep_b,
            "local_date": "2025-11-20",  # Week 47 Thursday
            "meal": "dinner",
            "diet_type_id": "laktos",
            "marked": True,
        },
    )
    assert r_mark_b1.status_code in (200, 201)

    # Call overview UI
    r_ui = client_admin.get(
        f"/ui/weekview_overview?site_id={site_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)

    # Weekly summaries (diet names mirror ids for now)
    assert "gluten: 4" in html  # Dep A
    assert "laktos: 1" in html  # Dep B

    # Per-day indicators (simple presence of diet-dot at least for 3 marked days)
    assert html.count("diet-dot") >= 3

    # No 'Ingen specialkost registrerad' when marks exist for both rows
    assert "Ingen specialkost registrerad" not in html
