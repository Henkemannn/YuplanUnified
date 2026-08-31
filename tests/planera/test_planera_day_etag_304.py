import uuid
from datetime import date


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_day_etag_304(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    d = date(2025, 11, 22).isoformat()

    from core.db import create_all, get_session
    from sqlalchemy import text
    import os
    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "SiteZ"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_id, "s": site_id, "n": "AvdZ"})
            db.commit()
        finally:
            db.close()
        reg = getattr(app, "feature_registry", None)
        if reg:
            # Force enable irrespective of prior state
            if not reg.has("ff.planera.enabled"):
                reg.add("ff.planera.enabled")
            reg.set("ff.planera.enabled", True)

    r1 = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag and etag.startswith('W/"planera:day:')

    r2 = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers={**_h("admin"), "If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.get_data(as_text=True) == ""


def test_planera_day_compute_day_counts_default_select_specialkost(client_admin):
    app = client_admin.application
    day = date(2025, 11, 24).isoformat()

    from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
    from core.planera_service import PlaneraService
    from core.weekview.service import WeekviewService

    with app.app_context():
        site, _ = SitesRepo().create_site(name=f"PlaneraSite-{uuid.uuid4().hex[:8]}", tenant_id=1)
        dept, _ = DepartmentsRepo().create_department(
            site_id=site["id"],
            name=f"AvdP-{uuid.uuid4().hex[:8]}",
            resident_count_mode="fixed",
            resident_count_fixed=10,
        )
        diet_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=True)
        DepartmentsRepo().upsert_department_diet_defaults(
            dept["id"],
            0,
            [{"diet_type_id": diet_id, "default_count": 2}],
        )

        result = PlaneraService(WeekviewService()).compute_day(
            tenant_id=1,
            site_id=site["id"],
            iso_date=day,
            departments=[(dept["id"], dept["name"])],
        )

    lunch = result["departments"][0]["meals"]["lunch"]
    special = next((item for item in lunch["special_diets"] if item["diet_type_id"] == str(diet_id)), None)

    assert lunch["residents_total"] == 10
    assert special is not None and special["count"] == 2
    assert lunch["normal_diet_count"] == 8
