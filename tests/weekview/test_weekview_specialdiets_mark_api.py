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
def test_toggle_specialdiet_mark_with_etag(client_admin):
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
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_id, "s": site_id, "n": "Avd E"})
            db.commit()
        finally:
            db.close()

    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    # Ensure session site context matches our seeded site
    client_admin.post(
        "/ui/select-site",
        data={"site_id": site_id, "next": "/"},
        headers=_h("admin"),
    )
    r0 = client_admin.get(base, headers=_h("admin"))
    assert r0.status_code == 200 and ETAG_RE.match(r0.headers.get("ETag") or "")
    etag = r0.headers.get("ETag")

    # Set mark (Mon lunch, gluten)
    r_set = client_admin.patch(
        "/api/weekview/specialdiets/mark",
        headers={**_h("editor"), "If-Match": etag},
        json={
            "site_id": site_id,
            "department_id": dep_id,
            "local_date": "2025-11-24",  # Monday week 48
            "meal": "lunch",
            "diet_type_id": "gluten",
            "marked": True,
        },
    )
    assert r_set.status_code in (200, 201)
    etag2 = r_set.headers.get("ETag") or etag

    # Verify GET shows mark present in raw marks
    r1 = client_admin.get(base, headers=_h("admin"))
    assert r1.status_code == 200
    marks = r1.get_json()["department_summaries"][0].get("marks", [])
    assert any(m["day_of_week"] == 1 and m["meal"] == "lunch" and m["diet_type"] == "gluten" and m["marked"] for m in marks)

    # Clear mark using the new ETag
    r_clr = client_admin.patch(
        "/api/weekview/specialdiets/mark",
        headers={**_h("editor"), "If-Match": etag2},
        json={
            "site_id": site_id,
            "department_id": dep_id,
            "local_date": "2025-11-24",
            "meal": "lunch",
            "diet_type_id": "gluten",
            "marked": False,
        },
    )
    assert r_clr.status_code in (200, 201)

    # Using stale ETag should fail
    r_stale = client_admin.patch(
        "/api/weekview/specialdiets/mark",
        headers={**_h("editor"), "If-Match": etag},
        json={
            "site_id": site_id,
            "department_id": dep_id,
            "local_date": "2025-11-24",
            "meal": "lunch",
            "diet_type_id": "gluten",
            "marked": True,
        },
    )
    assert r_stale.status_code == 412
