from tests._auth_site_helpers import login_bound_user
HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_minimal_marked(app):
    from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
    from core.weekview.repo import WeekviewRepo

    with app.app_context():
        site, _ = SitesRepo().create_site(name="Test Site", tenant_id=1)
        department, _ = DepartmentsRepo().create_department(
            site_id=site["id"],
            name="Avd Alpha",
            resident_count_mode="fixed",
            resident_count_fixed=5,
        )
        diet_id = DietTypesRepo().create(
            site_id=site["id"],
            tenant_id=1,
            name="Gluten",
            semantics="atomic",
        )
        DepartmentsRepo().upsert_department_diet_defaults(
            department["id"],
            0,
            [{"diet_type_id": str(diet_id), "default_count": 1}],
        )
        year, week = 2026, 8
        WeekviewRepo().apply_operations(
            tenant_id=1,
            year=year,
            week=week,
            department_id=department["id"],
            ops=[
                {
                    "day_of_week": 1,
                    "meal": "lunch",
                    "diet_type": str(diet_id),
                    "marked": True,
                }
            ],
        )
    return site["id"], department["id"], year, week


def test_weekview_site_level_marked_ring(app_session):
    client = app_session.test_client()
    site_id, _dep, year, week = _seed_minimal_marked(app_session)
    login_bound_user(client, site_id=site_id)
    rv = client.get(f"/ui/weekview?site_id={site_id}&year={year}&week={week}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Marked cell present
    assert 'diet-cell marked' in html
    # CSS selector present in unified_ui.css
    with open('static/unified_ui.css', 'r', encoding='utf-8') as f:
        css = f.read()
    assert '.weekview-all .weekview td.diet-cell.marked::before' in css
