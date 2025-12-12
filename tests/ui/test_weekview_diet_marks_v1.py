import uuid
from datetime import date


def _h(role="admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_weekview_diets_mark_and_report_integration(client_admin):
    app = client_admin.application
    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.admin_repo import DietTypesRepo, DepartmentsRepo, DietDefaultsRepo

    with app.app_context():
        create_all()
        db = get_session()
        try:
            site_id = str(uuid.uuid4())
            dep_id = str(uuid.uuid4())
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), {"i": site_id, "n": "Site D"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0) ON CONFLICT(id) DO NOTHING"), {"i": dep_id, "s": site_id, "n": "Avd D"})
            db.commit()
        finally:
            db.close()

    # Create one diet type and set default=2 for department
    dtype_id = DietTypesRepo().create(tenant_id=1, name="Gluten", default_select=False)
    ver = DepartmentsRepo().get_version(dep_id) or 0
    DepartmentsRepo().upsert_department_diet_defaults(dep_id, ver, [{"diet_type_id": str(dtype_id), "default_count": 2}])

    # Current week
    today = date.today()
    iy, iw = today.isocalendar()[0], today.isocalendar()[1]

    # GET Weekview shows the diet label
    r0 = client_admin.get(f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={iy}&week={iw}", headers=_h("admin"))
    assert r0.status_code == 200
    html0 = r0.get_data(as_text=True)
    assert "Gluten" in html0

    # POST mark Monday lunch for this diet
    resp = client_admin.post(
        "/ui/weekview/diets/save",
        data={
            "site_id": site_id,
            "department_id": dep_id,
            "year": str(iy),
            "week": str(iw),
            "mark": [f"1|lunch|{dtype_id}"],
        },
        headers=_h("admin"),
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Verify persistence via WeekviewRepo
    from core.weekview.repo import WeekviewRepo
    payload = WeekviewRepo().get_weekview(tenant_id=1, year=iy, week=iw, department_id=dep_id)
    summaries = payload.get("department_summaries") or []
    marks = summaries[0].get("marks") if summaries else []
    assert any(int(m.get("day_of_week")) == 1 and m.get("meal") == "lunch" and str(m.get("diet_type")) == str(dtype_id) and bool(m.get("marked")) for m in marks)

    # Sanity: admin weekly report page renders 200 for this week
    rr = client_admin.get(f"/ui/admin/report/week?year={iy}&week={iw}&department_id={dep_id}&view=day", headers=_h("admin"))
    assert rr.status_code == 200
