from tests._auth_site_helpers import login_bound_user
import uuid
from sqlalchemy import text

HEADERS_PORTAL = {"X-User-Role": "unit_portal", "X-Tenant-Id": "1"}
HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
HEADERS_USER = {"X-User-Role": "user", "X-Tenant-Id": "1"}


def _seed_site_dep_week_with_menu():
    from core.db import get_session
    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep_id = str(uuid.uuid4())
        year, week = 2025, 2
        # Create site/department
        db.execute(text("INSERT INTO sites(id, name, tenant_id, version) VALUES(:i,:n,1,0)"), {"i": site_id, "n": "PortalSite"})
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES(:i,:s,:n,'fixed',8,'PRIVATE_ADMIN_NOTE_DO_NOT_EXPOSE',0)"), {"i": dep_id, "s": site_id, "n": "Avd Portal"})
        db.commit()
    finally:
        db.close()
    from core.admin_repo import DepartmentsRepo, DietTypesRepo

    diet_repo = DietTypesRepo()
    diet_ids = {
        name: diet_repo.create(
            site_id=site_id,
            tenant_id=1,
            name=name,
            semantics="atomic",
        )
        for name in ("Gluten", "Laktos")
    }
    DepartmentsRepo().upsert_department_diet_defaults(
        dep_id,
        0,
        [
            {"diet_type_id": str(diet_ids["Gluten"]), "default_count": 2},
            {"diet_type_id": str(diet_ids["Laktos"]), "default_count": 1},
        ],
    )
    return site_id, dep_id, year, week


def test_portal_week_enhetsportal_view(app_session):
    client = app_session.test_client()
    site_id, dep_id, year, week = _seed_site_dep_week_with_menu()

    login_bound_user(client, site_id=site_id, role="unit_portal", department_id=dep_id)

    # GET portal week as portal role
    r = client.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}", headers=HEADERS_PORTAL)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Residents and diet defaults summary
    assert "Boendeantal:" in html and "8" in html
    assert "Specialkost på avdelningen" in html
    assert "Gluten" in html and "Laktos" in html
    # Notes must stay private
    assert "PRIVATE_ADMIN_NOTE_DO_NOT_EXPOSE" not in html
    assert "Faktaruta" not in html
    # Ensure data-can-choose-lunch attribute appears on lunch blocks
    assert 'data-can-choose-lunch="' in html
    # Dinner block indicates read-only
    assert "KVÄLLSMAT" in html
    assert "Endast menyvisning" in html
    # Status badge present (complete or not)
    assert ("Veckan är klar" in html) or ("Veckan är inte klar" in html)


def test_portal_week_rbac(app_session):
    client = app_session.test_client()
    site_id, dep_id, year, week = _seed_site_dep_week_with_menu()
    r_bad = client.get(f"/ui/portal/week?site_id={site_id}&department_id={dep_id}&year={year}&week={week}")
    assert r_bad.status_code in (302, 403, 401)
