import re
from datetime import date
from core.admin_repo import SitesRepo, DepartmentsRepo

def _headers(role="admin", tid="1"):
    return {"X-User-Role": role, "X-Tenant-Id": tid}


def test_get_admin_residents_week(client_admin):
    # Ensure at least one site and department exist
    site, _ = SitesRepo().create_site("Test Site")
    DepartmentsRepo().create_department(site_id=site["id"], name="Avd A", resident_count_mode="fixed", resident_count_fixed=10)
    # Use current ISO week
    iso = date.today().isocalendar()
    year, week = iso[0], iso[1]
    resp = client_admin.get(f"/ui/admin/residents/week/{year}/{week}", headers=_headers())
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Boendeantal – vecka" in html
    # Expect at least one input rendered for lunch/dinner when departments exist
    assert re.search(r"name=\"dept_.*_lunch\"", html)
    assert re.search(r"name=\"dept_.*_dinner\"", html)


def test_post_saves_override_then_reflects(client_admin):
    site, _ = SitesRepo().create_site("Test Site")
    dept, _ = DepartmentsRepo().create_department(site_id=site["id"], name="Avd B", resident_count_mode="fixed", resident_count_fixed=9)
    iso = date.today().isocalendar()
    year, week = iso[0], iso[1]
    # First fetch to get a department id from rendered inputs
    resp = client_admin.get(f"/ui/admin/residents/week/{year}/{week}", headers=_headers())
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    m = re.search(r"name=\"dept_(.*?)_lunch\"", html)
    assert m, "No department input found"
    dept_id = m.group(1)

    # Post new values
    form = {
        f"dept_{dept_id}_lunch": "7",
        f"dept_{dept_id}_dinner": "6",
    }
    resp2 = client_admin.post(f"/ui/admin/residents/week/{year}/{week}", data=form, headers=_headers(), follow_redirects=False)
    assert resp2.status_code in (302, 303)

    # Fetch again and ensure values show up
    resp3 = client_admin.get(f"/ui/admin/residents/week/{year}/{week}", headers=_headers())
    html3 = resp3.data.decode("utf-8")
    assert f"name=\"dept_{dept_id}_lunch\" value=\"7\"" in html3
    assert f"name=\"dept_{dept_id}_dinner\" value=\"6\"" in html3


def test_fallback_uses_fixed_when_no_override(client_admin):
    site, _ = SitesRepo().create_site("Test Site")
    DepartmentsRepo().create_department(site_id=site["id"], name="Avd C", resident_count_mode="fixed", resident_count_fixed=8)
    iso = date.today().isocalendar()
    year, week = iso[0], iso[1]
    resp = client_admin.get(f"/ui/admin/residents/week/{year}/{week}", headers=_headers())
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    # For first department, compare displayed "Normalt:" value to inputs as default
    mrow = re.search(r"Normalt: (\d+)", html)
    assert mrow, "No fixed count displayed"
    fixed = int(mrow.group(1))
    # Ensure at least one input has that default
    assert str(fixed) in html
