from __future__ import annotations

from datetime import date

from sqlalchemy import text

from core.admin_repo import DietTypesRepo
from core.admin_repo import DietDefaultsRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo


def _login(client, *, role: str, site_id: str, tenant_id: int = 1, user_id: int = 1) -> None:
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = role
        sess["tenant_id"] = tenant_id
        sess["site_id"] = site_id


def _seed_site(app, *, site_id: str, site_name: str) -> None:
    from core.db import get_session

    conn = get_session()
    try:
        conn.execute(text("INSERT INTO sites(id, tenant_id, name) VALUES(:id, 1, :name) ON CONFLICT(id) DO UPDATE SET tenant_id=1, name=excluded.name"), {"id": site_id, "name": site_name})
        conn.commit()
    finally:
        conn.close()


def _seed_department(site_id: str, department_id: str, department_name: str) -> None:
    from core.db import get_session

    conn = get_session()
    try:
        conn.execute(
            text(
                "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) VALUES(:id, :site_id, :name, 'fixed', 5) ON CONFLICT(id) DO UPDATE SET site_id=excluded.site_id, name=excluded.name, resident_count_mode='fixed', resident_count_fixed=5"
            ),
            {"id": department_id, "site_id": site_id, "name": department_name},
        )
        conn.commit()
    finally:
        conn.close()


def _seed_legacy_defaults(site_id: str, department_id: str) -> int:
    dt_repo = DietTypesRepo()
    legacy_id = dt_repo.create(site_id=site_id, name="Legacy Kost", default_select=False, semantics="atomic")
    DietDefaultsRepo().list_for_department(department_id)
    from core.db import get_session

    conn = get_session()
    try:
        columns = {
            row[1]
            for row in conn.execute(text("pragma table_info('department_diet_defaults')")).fetchall()
        }
        if "always_mark" in columns:
            statement = text(
                "INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count, always_mark) VALUES(:dept, :dt, 2, 0) "
                "ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count, always_mark=excluded.always_mark"
            )
        else:
            statement = text(
                "INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:dept, :dt, 2) "
                "ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count"
            )
        conn.execute(
            statement,
            {"dept": department_id, "dt": str(legacy_id)},
        )
        conn.commit()
    finally:
        conn.close()
    return legacy_id


def _seed_cohort(site_id: str, department_id: str):
    repo = DietTypesRepo()
    timbal = repo.create(site_id=site_id, name="Timbal", default_select=False, semantics="atomic")
    glutenfri = repo.create(site_id=site_id, name="Glutenfri", default_select=False, semantics="atomic")
    group = DepartmentRequirementGroupsRepo().create_group(department_id, 1, [timbal, glutenfri], label=None, primary_requirement_id=timbal)
    completion = DepartmentRequirementGroupCompletionRepo()
    completion.set_marked(department_id, group["id"], date.fromisocalendar(2026, 37, 1), "lunch", True)
    return group["id"]


def test_admin_all_departments_renders_cohort_row_read_only(client_admin):
    site_id = "site-cohort-admin"
    cohort_dept = "dept-cohort-admin"
    legacy_dept = "dept-legacy-admin"
    _seed_site(client_admin.application, site_id=site_id, site_name="Admin Cohort Site")
    _seed_department(site_id, cohort_dept, "Kohort Avd")
    _seed_department(site_id, legacy_dept, "Legacy Avd")
    group_id = _seed_cohort(site_id, cohort_dept)
    _seed_legacy_defaults(site_id, legacy_dept)
    _login(client_admin, role="admin", site_id=site_id)

    rv = client_admin.get(f"/ui/weekview?site_id={site_id}&year=2026&week=37", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'data-weekview-readonly="true"' in html
    assert html.count('<tr class="diet-row" data-row-kind="cohort"') == 1
    assert f'data-group-id="{group_id}"' in html
    assert 'Timbal + Glutenfri' in html
    assert 'disabled aria-disabled="true"' in html
    assert 'data-diet-type-id="' in html  # legacy rows remain rendered for the legacy department
    assert 'Inga specialkoster kopplade' not in html
    assert 'Inga specialkoster kopplade' not in html


def test_kitchen_all_departments_renders_cohort_row_disabled_and_legacy_rows_clickable(client_cook):
    site_id = "site-cohort-kitchen"
    cohort_dept = "dept-cohort-kitchen"
    legacy_dept = "dept-legacy-kitchen"
    _seed_site(client_cook.application, site_id=site_id, site_name="Kitchen Cohort Site")
    _seed_department(site_id, cohort_dept, "Kohort Avd")
    _seed_department(site_id, legacy_dept, "Legacy Avd")
    group_id = _seed_cohort(site_id, cohort_dept)
    _seed_legacy_defaults(site_id, legacy_dept)
    _login(client_cook, role="cook", site_id=site_id)

    rv = client_cook.get(f"/ui/kitchen/week?site_id={site_id}&year=2026&week=37", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert html.count('<tr class="diet-row" data-row-kind="cohort"') == 1
    assert f'data-group-id="{group_id}"' in html
    assert 'Timbal + Glutenfri' in html
    assert 'data-diet-type-id="' in html  # legacy rows still carry legacy payloads
    assert 'disabled aria-disabled="true"' not in html  # kitchen cohort rows with positive counts are clickable
    assert 'data-service-date="2026-09-07"' in html
    assert 'Inga specialkoster kopplade' not in html
    assert 'Inga specialkoster kopplade' not in html


def test_kitchen_legacy_row_keeps_clickable_contract_while_cohort_row_is_read_only(client_cook):
    site_id = "site-click-contract"
    cohort_dept = "dept-click-cohort"
    legacy_dept = "dept-click-legacy"
    _seed_site(client_cook.application, site_id=site_id, site_name="Click Contract Site")
    _seed_department(site_id, cohort_dept, "Kohort Avd")
    _seed_department(site_id, legacy_dept, "Legacy Avd")
    _seed_cohort(site_id, cohort_dept)
    _seed_legacy_defaults(site_id, legacy_dept)
    _login(client_cook, role="cook", site_id=site_id)

    rv = client_cook.get(f"/ui/kitchen/week?site_id={site_id}&year=2026&week=37", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)

    legacy_button_start = html.index('data-row-kind="legacy"')
    legacy_button_slice = html[legacy_button_start: html.index('</button>', legacy_button_start)]
    assert 'data-diet-type-id="' in legacy_button_slice
    assert 'disabled' not in legacy_button_slice

    cohort_button_start = html.index('data-row-kind="cohort"')
    cohort_button_slice = html[cohort_button_start: html.index('</button>', cohort_button_start)]
    assert 'data-group-id="' in cohort_button_slice
    assert 'data-diet-type-id="' not in cohort_button_slice
    assert 'data-service-date="2026-09-07"' in cohort_button_slice
    assert 'disabled aria-disabled="true"' not in cohort_button_slice
    assert 'Inga specialkoster kopplade' not in html
    assert 'Inga specialkoster kopplade' not in html


