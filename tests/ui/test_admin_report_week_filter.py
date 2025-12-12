import re

from core.admin_repo import SitesRepo, DepartmentsRepo
HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

def test_admin_report_week_has_filter_controls(app_session, client_admin):
    # Seed a site and one department so vm.departments is non-empty
    site, _ = SitesRepo().create_site("Test Site")
    DepartmentsRepo().create_department(site_id=site["id"], name="Avd Test", resident_count_mode="fixed", resident_count_fixed=10)
    r = client_admin.get("/ui/admin/report/week?department_id=ALL", headers=HEADERS_ADMIN)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Year and week inputs
    assert "name=\"year\"" in html
    assert "name=\"week\"" in html
    # Minimal controls are present
    # Navigation links may appear when departments list renders; not required here
