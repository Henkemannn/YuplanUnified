import uuid
from datetime import date


def _h(role="admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_weekview_residents_post_persists_counts(client_admin):
    """
    Minimal end-to-end test:
    - Seed one site + department
    - POST residents (lunch=10, dinner=12) to /ui/weekview/residents/save
    - Follow redirect and assert 200
    - Verify DB (weekview_residents_count) contains saved values for the week
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    today = date.today()
    iso = today.isocalendar()
    year, week = iso[0], iso[1]

    # Seed DB: site + department
    from core.db import create_all, get_session
    from sqlalchemy import text
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"),
                {"i": site_id, "n": "WeekviewSite"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"
                ),
                {"i": dep_id, "s": site_id, "n": "Avd W"},
            )
            db.commit()
        finally:
            db.close()

    # POST residents save
    resp = client_admin.post(
        "/ui/weekview/residents/save",
        data={
            "site_id": site_id,
            "department_id": dep_id,
            "year": str(year),
            "week": str(week),
            "residents_lunch": "10",
            "residents_dinner": "12",
        },
        headers=_h("admin"),
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Verify via repo (preferred over brittle UI value match)
    from core.weekview.repo import WeekviewRepo
    repo = WeekviewRepo()
    payload = repo.get_weekview(tenant_id=1, year=year, week=week, department_id=dep_id)
    summaries = payload.get("department_summaries") or []
    assert summaries, "Expected department summaries after POST"
    counts = summaries[0].get("residents_counts") or []
    # Expect at least Monday entries for lunch and dinner with the posted values
    has_lunch = any(c for c in counts if c["day_of_week"] == 1 and c["meal"] == "lunch" and c["count"] == 10)
    has_dinner = any(c for c in counts if c["day_of_week"] == 1 and c["meal"] == "dinner" and c["count"] == 12)
    assert has_lunch and has_dinner
