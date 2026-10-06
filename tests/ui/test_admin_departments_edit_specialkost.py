import uuid
import re
import pytest
from datetime import date
from pathlib import Path

from flask import request

from core.db import get_session
from core.admin_repo import DietDefaultsRepo, DepartmentDietOverridesRepo, DietTypesRepo, DepartmentsRepo, SitesRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo
from core.department_requirement_group_weekview_projection import build_department_requirement_group_weekview_projection
from sqlalchemy import text


def _build_weekday_override_payload(*, group_id: str, primary_requirement_id: int, default_quantity: int, overrides: dict[tuple[int, str], int | None]) -> dict[str, str]:
    payload: dict[str, str] = {
        "group_id": str(group_id),
        "primary_requirement_id": str(primary_requirement_id),
        "default_quantity": str(default_quantity),
        "is_active": "1",
    }
    for weekday in range(1, 8):
        for meal in ("lunch", "dinner"):
            key = f"weekday_quantity_{group_id}_{weekday}_{meal}"
            value = overrides.get((weekday, meal), default_quantity)
            payload[key] = "" if value is None else str(value)
    return payload

def test_edit_form_shows_specialkost_heading(client_admin):
    # Create a department
    dep_id = str(uuid.uuid4())
    db = get_session()
    try:
        db.execute(text("INSERT INTO departments (id, site_id, name, resident_count_fixed, resident_count_mode, version) VALUES (:id, 1, 'Test', 5, 'fixed', 0)"), {"id": dep_id})
        db.commit()
    finally:
        db.close()
    r = client_admin.get(f"/ui/admin/departments/{dep_id}/edit")
    if r.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Kostbehov" in html
    assert "Standardvärden / avancerade inställningar" in html
    assert "app-shell__env-badge" in html
    assert '<div class="app-shell__card-meta">Vecka ' not in html


def test_edit_form_renders_compact_desktop_profile_and_section_closure(client_admin):
    site, _ = SitesRepo().create_site(f"Desktop UX site {uuid.uuid4()}")
    residence_id = str(uuid.uuid4())
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("INSERT INTO residences (id, site_id, name) VALUES (:id, :sid, :name)"), {"id": residence_id, "sid": site["id"], "name": "Solrosen"})
        db.commit()
    finally:
        db.close()
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Desktop UX",
        resident_count_mode="fixed",
        resident_count_fixed=12,
        residence_id=residence_id,
        notes="Avdelningschefen är sur på måndagar",
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")
    grp = DepartmentRequirementGroupsRepo().create_group(
        dep["id"],
        2,
        [timbal_id, glutenfri_id],
        label="Timbal + Glutenfri",
        primary_requirement_id=timbal_id,
    )

    from core.residents_schedule_repo import ResidentsScheduleRepo

    current_week = date.today().isocalendar()[1]
    ResidentsScheduleRepo().upsert_items(
        dep["id"],
        current_week,
        [
            {"weekday": 2, "meal": "lunch", "count": 11},
        ],
    )
    DepartmentRequirementGroupWeekdayOverridesRepo().set_override(str(grp["id"]), 2, "lunch", 1)

    r = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    css = Path("static/css/admin_departments.css").read_text(encoding="utf-8")
    admin_css = Path("static/css/unified_admin.css").read_text(encoding="utf-8")

    assert html.count('class="admin-department-profile__title">Avd Desktop UX<') == 1
    assert "Avdelningsprofil" not in html
    assert "Veckovariationer" not in html
    assert "Hantera veckans val" not in html
    assert "Menyval" not in html
    assert "id=\"name\"" not in html
    assert "id=\"residence_id\"" not in html
    assert "id=\"resident_count\"" not in html
    assert "id=\"notes\"" not in html
    assert "Avdelningen" in html
    assert "Redigera avdelning" in html
    assert "department-edit-modal" in html
    assert '<div class="ua-modal-inner">' in html
    assert 'action="/ui/admin/departments/' in html and '/edit"' in html
    assert 'id="department-edit-name"' in html
    assert 'id="department-edit-residence"' in html
    assert 'id="department-edit-resident-count"' in html
    assert 'id="department-edit-notes"' in html
    assert ".admin-department-edit-modal .ua-modal-inner" in css
    assert "max-width: 760px;" in css
    assert "backdrop-filter: none;" not in css
    assert "dialog.ua-modal::backdrop" in admin_css
    assert "backdrop-filter: blur(12px) saturate(120%);" in admin_css
    assert "Solrosen" in html
    assert "12 · Varierat" in html
    assert "Avdelningschefen är sur på måndagar" in html
    assert "Tis lunch 11" not in html
    assert "Serveringsanpassningar" in html
    assert "+ Lägg till kostbehov" in html
    assert "Timbal" in html
    assert "Glutenfri" in html
    assert "2 personer" in html
    assert 'admin-need-item__state' not in html
    assert html.count("Hantera variation") == 1
    assert "Redigera" in html
    assert 'id="need-modal"' in html
    assert '<div class="ua-modal-inner">' in html
    assert 'data-modal-target="#need-modal"' in html
    assert 'data-need-mode="create"' in html
    assert 'data-need-mode="edit"' in html
    assert 'id="need-modal-primary-requirement-id"' in html
    assert 'id="need-modal-modifier-requirement-ids"' in html
    assert html.count('+ Lägg till kostbehov') >= 2
    assert 'Välj ytterligare behov' not in html
    assert 'data-need-picker-toggle' in html
    assert 'data-need-picker-close' in html
    assert 'data-need-picker-search' in html
    assert 'Ytterligare kostbehov (valfritt)' in html
    assert 'admin-need-modal__chip' in html
    assert 'admin-need-modal__advanced' not in html
    assert 'name="is_active"' not in html
    assert 'Aktivt behov' not in html
    assert 'class="admin-need-item__body"' not in html
    assert 'admin-need-form--edit' not in html
    assert 'data-modal-target="#residents-variation-modal"' in html
    assert f'/ui/admin/departments/{dep["id"]}/edit"' in html
    assert f'/ui/admin/departments/{dep["id"]}/requirement-groups"' in html
    assert f'/ui/admin/departments/{dep["id"]}/edit/service-addons"' in html
    assert f'/ui/admin/departments/{dep["id"]}/variation"' in html
    assert 'aria-label="Lägg till boende"' not in html

def test_edit_post_saves_default_and_reads_back(client_admin):
    # Create a department and one diet type
    dep_id = str(uuid.uuid4())
    db = get_session()
    try:
        # Ensure tables exist in ephemeral sqlite used by tests
        from core.db import create_all
        create_all()
        db.execute(text("INSERT INTO departments (id, site_id, name, resident_count_fixed, resident_count_mode, version) VALUES (:id, 1, 'Test', 5, 'fixed', 0)"), {"id": dep_id})
        try:
            db.execute(text("INSERT INTO diet_types (id, tenant_id, name, default_select) VALUES (1, 1, 'Laktos', 0)"))
        except Exception:
            pytest.skip("Diet types table not available")
        db.commit()
    finally:
        db.close()
    # GET to fetch version
    r0 = client_admin.get(f"/ui/admin/departments/{dep_id}/edit")
    if r0.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    assert r0.status_code == 200
    # POST with one default
    r1 = client_admin.post(f"/ui/admin/departments/{dep_id}/edit/diets", data={
        "diet_default_1": "3",
    })
    assert r1.status_code in (302, 303)
    # Verify via repo
    from core.admin_repo import DietDefaultsRepo
    items = DietDefaultsRepo().list_for_department(dep_id)
    found = {int(it["diet_type_id"]): int(it.get("default_count", 0)) for it in items}
    assert found.get(1) == 3


def test_edit_form_allows_missing_diet_default_keys(client_admin):
    dep_id = str(uuid.uuid4())
    db = get_session()
    try:
        from core.db import create_all

        create_all()
        db.execute(
            text(
                "INSERT INTO departments (id, site_id, name, resident_count_fixed, resident_count_mode, version) "
                "VALUES (:id, 1, 'Test Missing Defaults', 5, 'fixed', 0)"
            ),
            {"id": dep_id},
        )
        try:
            db.execute(text("INSERT INTO diet_types (id, tenant_id, name, default_select) VALUES (1, 1, 'Laktos', 0)"))
            db.execute(text("INSERT INTO diet_types (id, tenant_id, name, default_select) VALUES (7, 1, 'Gluten', 0)"))
        except Exception:
            pytest.skip("Diet types table not available")
        db.commit()
    finally:
        db.close()

    r = client_admin.get(f"/ui/admin/departments/{dep_id}/edit")
    if r.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Laktos" in html
    assert "Gluten" in html


def test_edit_form_groups_specialkost_by_category(client_admin):
    dep_id = str(uuid.uuid4())
    db = get_session()
    try:
        from core.db import create_all

        create_all()
        db.execute(
            text(
                "INSERT INTO departments (id, site_id, name, resident_count_fixed, resident_count_mode, version) "
                "VALUES (:id, 1, 'Test Grouped Specialkost', 5, 'fixed', 0)"
            ),
            {"id": dep_id},
        )
        db.commit()
    finally:
        db.close()

    repo = DietTypesRepo()
    repo.create(site_id="1", name="Timbal Grupp Dep", diet_family="Textur", default_select=False)
    repo.create(site_id="1", name="Ej Fisk Grupp Dep", diet_family="Allergi / Exkludering", default_select=False)

    r = client_admin.get(f"/ui/admin/departments/{dep_id}/edit")
    if r.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "admin-need-item" in html
    assert "+ Lägg till behov" in html
    assert "<details class=\"specialkost-edit-group\" open>" in html
    assert "Textur" in html
    assert "Allergi / Exkludering" in html
    assert "Timbal Grupp Dep" in html
    assert "Ej Fisk Grupp Dep" in html


def test_edit_form_groups_specialkost_by_family_inside_category(client_admin):
    dep_id = str(uuid.uuid4())
    db = get_session()
    try:
        from core.db import create_all

        create_all()
        db.execute(
            text(
                "INSERT INTO departments (id, site_id, name, resident_count_fixed, resident_count_mode, version) "
                "VALUES (:id, 1, 'Test Family Group Specialkost', 5, 'fixed', 0)"
            ),
            {"id": dep_id},
        )
        db.commit()
    finally:
        db.close()

    repo = DietTypesRepo()
    repo.create(site_id="1", name="Timbal", diet_family="Textur", default_select=False)
    repo.create(site_id="1", name="Timbal -Fisk", diet_family="Textur", default_select=False)
    repo.create(site_id="1", name="Grovpaté", diet_family="Textur", default_select=False)

    r = client_admin.get(f"/ui/admin/departments/{dep_id}/edit")
    if r.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "data-specialkost-subgroup" in html
    assert ">Timbal<" in html
    assert ">Grovpaté<" in html


def test_edit_form_renders_requirement_groups_and_can_create_update(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement group UI site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Requirement UI",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")
    laktosfri_id = DietTypesRepo().create(site_id=site["id"], name="Laktosfri", default_select=False, semantics="atomic")
    flytande_id = DietTypesRepo().create(site_id=site["id"], name="Flytande kost", default_select=False, semantics="atomic")

    dept_repo = DepartmentsRepo()
    dept_repo.upsert_department_diet_defaults(
        dep["id"],
        expected_version=0,
        items=[
            {"diet_type_id": timbal_id, "default_count": 1},
            {"diet_type_id": glutenfri_id, "default_count": 1},
            {"diet_type_id": flytande_id, "default_count": 1},
        ],
    )

    defaults_before = DietDefaultsRepo().list_for_department(dep["id"])
    diet_count_before = len(DietTypesRepo().list_all(site_id=site["id"]))

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    page = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Registrerade kostbehov" in html
    assert "Kostbehov" in html
    create_select = re.search(r'<select id="need-modal-primary-requirement-id"[^>]*>(.*?)</select>', html, re.S)
    assert create_select is not None
    create_options = create_select.group(1)
    assert "Timbal" in create_options
    assert "Glutenfri" in create_options
    assert "Flytande kost" in create_options
    assert "Laktosfri" in create_options
    assert html.count('+ Lägg till kostbehov') >= 1
    assert 'data-need-picker-toggle' in html
    assert 'data-need-picker-search' in html
    assert 'admin-need-modal__chip' in html
    assert 'admin-need-modal__advanced' not in html
    assert 'name="is_active"' not in html

    create_resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data={
            "primary_requirement_id": str(timbal_id),
            "default_quantity": "2",
            "is_active": "1",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert create_resp.status_code == 200

    repo = DepartmentRequirementGroupsRepo()
    groups = repo.list_for_department(dep["id"])
    assert len(groups) == 1
    group_id = str(groups[0]["id"])
    defaults_after_create = DietDefaultsRepo().list_for_department(dep["id"])
    diet_count_after_create = len(DietTypesRepo().list_all(site_id=site["id"]))
    assert defaults_after_create == defaults_before
    assert diet_count_after_create == diet_count_before

    update_resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data={
            "group_id": group_id,
            "primary_requirement_id": str(timbal_id),
            "modifier_requirement_ids": [str(glutenfri_id)],
            "default_quantity": "3",
            "is_active": "1",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert update_resp.status_code == 200

    reread = repo.get_group(group_id)
    assert reread is not None
    assert reread["primary_requirement_id"] == timbal_id
    assert reread["default_quantity"] == 3


def test_specialkost_create_path_seeds_atomic_requirement_types_for_department_edit(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement catalog create site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Requirement Create Path",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    create_resp = client_admin.post(
        "/ui/admin/specialkost/new",
        data={"name": "Laktosfri", "diet_family": "Allergi / Exkludering", "default_select": ""},
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert create_resp.status_code == 200

    page = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Laktosfri" in html
    assert 'id="need-modal-primary-requirement-id"' in html
    assert 'name="is_active"' not in html
    assert 'admin-need-modal__advanced' not in html

    types = DietTypesRepo().list_all(site_id=site["id"])
    created = next(row for row in types if str(row.get("name")) == "Laktosfri")
    assert created["semantics"] == "atomic"
    assert str(created["requirement_key"]).startswith("req_")


def test_real_site_create_path_exposes_behovstyp_immediately(client_admin):
    from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo

    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    site_resp = client_admin.post("/admin/sites", json={"name": f"Live Catalog Site {uuid.uuid4()}"}, headers=headers)
    assert site_resp.status_code == 201
    site = site_resp.get_json()

    dept_resp = client_admin.post(
        "/admin/departments",
        json={"site_id": site["id"], "name": "Avd Live", "resident_count_mode": "fixed", "resident_count_fixed": 10},
        headers=headers,
    )
    assert dept_resp.status_code == 201
    department = dept_resp.get_json()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    edit_resp = client_admin.get(f"/ui/admin/departments/{department['id']}/edit", headers=headers)
    assert edit_resp.status_code == 200
    html = edit_resp.get_data(as_text=True)
    assert "Vilket kostbehov gäller?" in html
    assert 'id="need-modal-primary-requirement-id"' in html
    assert 'name="is_active"' not in html
    assert 'admin-need-modal__advanced' not in html
    assert "Timbal" in html or "Glutenfri" in html

    rows = DietTypesRepo().list_all(site_id=site["id"])
    requirement_id = next(row["id"] for row in rows if row["semantics"] == "atomic")

    group = DepartmentRequirementGroupsRepo().create_group(
        department["id"],
        1,
        [requirement_id],
        label="Immediate registered need",
    )

    reread_page = client_admin.get(f"/ui/admin/departments/{department['id']}/edit", headers=headers)
    assert reread_page.status_code == 200
    reread_html = reread_page.get_data(as_text=True)
    assert "1 person" in reread_html
    assert 'admin-need-item__state' not in reread_html
    assert 'data-need-mode="edit"' in reread_html
    assert f'data-need-group-id="{group["id"]}"' in reread_html
    assert group["requirements"][0]["dietary_type_id"] == requirement_id
    assert group["requirements"][0]["semantics"] == "atomic"

    reread = DepartmentRequirementGroupsRepo().list_for_department(department["id"])
    assert len(reread) == 1
    assert reread[0]["requirements"][0]["dietary_type_id"] == requirement_id


def test_edit_form_saves_residents_variation(client_admin):
    site, _ = SitesRepo().create_site(f"Variation UI site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Variation UI",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    page = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200

    resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/variation",
        data={
            "selected_week": "12",
            "selected_week_override": "12",
            "mode": "week",
            "day_1_lunch": "7",
            "day_1_dinner": "8",
            "day_2_lunch": "9",
            "day_2_dinner": "10",
            "day_3_lunch": "11",
            "day_3_dinner": "12",
            "day_4_lunch": "13",
            "day_4_dinner": "14",
            "day_5_lunch": "15",
            "day_5_dinner": "16",
            "day_6_lunch": "17",
            "day_6_dinner": "18",
            "day_7_lunch": "19",
            "day_7_dinner": "20",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200

    from core.residents_schedule_repo import ResidentsScheduleRepo

    rows = ResidentsScheduleRepo().get_week(dep["id"], 12)
    found = {(int(row["weekday"]), str(row["meal"])): int(row["count"]) for row in rows}
    assert found[(1, "lunch")] == 7
    assert found[(1, "dinner")] == 8
    assert found[(7, "dinner")] == 20


def test_edit_form_allows_site_catalog_requirement_creation_without_department_defaults(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement group clean create site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Clean Create",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")
    laktosfri_id = DietTypesRepo().create(site_id=site["id"], name="Laktosfri", default_select=False, semantics="atomic")
    DietTypesRepo().create(site_id=site["id"], name="Flytande kost", default_select=False, semantics="atomic")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    page = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Inga registrerade kostbehov ännu." in html
    assert "Standardvärden / avancerade inställningar" in html
    assert 'id="need-modal-modifier-requirement-ids"' in html
    assert 'data-need-picker-panel' in html
    assert 'data-need-picker-list' in html
    assert 'data-need-picker-count' in html
    assert re.search(r'<div class="admin-need-modal__picker"[^>]*data-need-picker[^>]*hidden', html)
    assert 'data-need-picker-close' in html

    resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data={
            "primary_requirement_id": str(laktosfri_id),
            "modifier_requirement_ids": [str(glutenfri_id)],
            "default_quantity": "2",
            "is_active": "1",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Inga registrerade behov ännu." not in html
    assert html.count("Hantera variation") == 1
    assert "Standardvärden / avancerade inställningar" in html
    assert html.count('+ Lägg till kostbehov') >= 2
    assert 'Välj ytterligare behov' not in html
    assert 'data-need-picker-panel' in html
    assert 'data-need-picker-list' in html
    assert 'data-need-picker-count' in html
    assert re.search(r'<div class="admin-need-modal__picker"[^>]*data-need-picker[^>]*hidden', html)
    assert 'data-need-picker-close' in html

    groups = DepartmentRequirementGroupsRepo().list_for_department(dep["id"])
    assert len(groups) == 1
    group = groups[0]
    assert group["default_quantity"] == 2
    assert group["primary_requirement_id"] == laktosfri_id
    assert {item["dietary_type_id"] for item in group["requirements"]} == {laktosfri_id, glutenfri_id}
    assert 'data-variation-focus-group-id=' not in html
    assert f'name="need_day_{group["id"]}_1_lunch"' in html


def test_edit_form_creates_active_kostbehov_without_active_field_and_preserves_existing_state(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement group active semantics site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Active Semantics",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    page = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'name="is_active"' not in html

    create_resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data={
            "primary_requirement_id": str(timbal_id),
            "modifier_requirement_ids": [str(glutenfri_id)],
            "default_quantity": "2",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert create_resp.status_code == 200

    repo = DepartmentRequirementGroupsRepo()
    groups = repo.list_for_department(dep["id"])
    assert len(groups) == 1
    created = groups[0]
    assert created["is_active"] is True
    assert {item["dietary_type_id"] for item in created["requirements"]} == {timbal_id, glutenfri_id}


def test_edit_form_can_remove_kostbehov_and_register_it_again_later(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement remove site {uuid.uuid4()}")
    dep_a, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Remove A",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    dep_b, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Remove B",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")

    repo = DepartmentRequirementGroupsRepo()
    active_group = repo.create_group(
        dep_a["id"],
        2,
        [timbal_id, glutenfri_id],
        label="Timbal + Glutenfri",
        primary_requirement_id=timbal_id,
    )
    other_group = repo.create_group(
        dep_b["id"],
        1,
        [timbal_id, glutenfri_id],
        label="Timbal + Glutenfri B",
        primary_requirement_id=timbal_id,
    )
    DepartmentRequirementGroupWeekdayOverridesRepo().set_override(active_group["id"], 4, "lunch", 1)
    DepartmentRequirementGroupWeekdayOverridesRepo().set_override(active_group["id"], 4, "dinner", 0)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    page = client_admin.get(f"/ui/admin/departments/{dep_a['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'admin-need-item__remove-trigger' not in html
    assert 'data-need-remove-start' in html
    assert 'data-need-remove-state' in html

    remove_resp = client_admin.post(
        f"/ui/admin/departments/{dep_a['id']}/requirement-groups",
        data={
            "group_id": str(active_group["id"]),
            "remove_request": "1",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert remove_resp.status_code == 200
    removed_html = remove_resp.get_data(as_text=True)
    assert "Kostbehovet togs bort från avdelningen." in removed_html
    assert "Timbal + Glutenfri" not in removed_html
    removed_group = DepartmentRequirementGroupsRepo().get_group(active_group["id"])
    assert removed_group is not None and removed_group["is_active"] is False
    assert DepartmentRequirementGroupWeekdayOverridesRepo().list_for_group(active_group["id"]) == [
        {"group_id": str(active_group["id"]), "weekday": 4, "meal_key": "dinner", "quantity": 0},
        {"group_id": str(active_group["id"]), "weekday": 4, "meal_key": "lunch", "quantity": 1},
    ]

    projection = build_department_requirement_group_weekview_projection(
        tenant_id=1,
        site_id=site["id"],
        department_id=dep_a["id"],
        service_date=date(2026, 10, 8),
        meal_key="lunch",
    )
    assert projection.needs == ()

    other_projection = build_department_requirement_group_weekview_projection(
        tenant_id=1,
        site_id=site["id"],
        department_id=dep_b["id"],
        service_date=date(2026, 10, 8),
        meal_key="lunch",
    )
    assert other_projection.needs and other_projection.needs[0].effective_quantity == 1

    catalog = DietTypesRepo().list_all(site_id=site["id"])
    assert {row["name"] for row in catalog} >= {"Timbal", "Glutenfri"}

    readd_resp = client_admin.post(
        f"/ui/admin/departments/{dep_a['id']}/requirement-groups",
        data={
            "primary_requirement_id": str(timbal_id),
            "modifier_requirement_ids": [str(glutenfri_id)],
            "default_quantity": "2",
            "is_active": "1",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert readd_resp.status_code == 200
    active_groups = [group for group in DepartmentRequirementGroupsRepo().list_for_department(dep_a["id"]) if group["is_active"]]
    assert len(active_groups) == 1
    assert {item["dietary_type_id"] for item in active_groups[0]["requirements"]} == {timbal_id, glutenfri_id}


def test_remove_post_redirects_and_keeps_payload_intact(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement remove request site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Remove Request",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")
    repo = DepartmentRequirementGroupsRepo()
    group = repo.create_group(
        dep["id"],
        2,
        [timbal_id, glutenfri_id],
        label="Timbal + Glutenfri",
        primary_requirement_id=timbal_id,
    )

    captured: dict[str, dict[str, str]] = {}

    def capture_request() -> None:
        if request.method == "POST" and request.path.endswith("/requirement-groups"):
            captured["form"] = request.form.to_dict(flat=True)

    client_admin.application.before_request_funcs.setdefault(None, []).append(capture_request)
    try:
        with client_admin.session_transaction() as sess:
            sess["site_id"] = site["id"]

        resp = client_admin.post(
            f"/ui/admin/departments/{dep['id']}/requirement-groups",
            data={
                "group_id": str(group["id"]),
                "remove_request": "1",
                "primary_requirement_id": str(timbal_id),
                "default_quantity": "2",
            },
            follow_redirects=False,
            headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
        )
    finally:
        client_admin.application.before_request_funcs.get(None, []).remove(capture_request)

    assert captured["form"]["group_id"] == str(group["id"])
    assert captured["form"]["remove_request"] == "1"
    assert captured["form"]["primary_requirement_id"] == str(timbal_id)
    assert captured["form"]["default_quantity"] == "2"
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/ui/admin/departments/{dep['id']}/edit")

    follow = client_admin.get(resp.headers["Location"], headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert follow.status_code == 200
    assert repo.get_group(group["id"]) is not None
    assert repo.get_group(group["id"])["is_active"] is False


def test_edit_form_rejects_zero_quantity_for_active_kostbehov(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement zero quantity site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Zero Quantity",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data={
            "primary_requirement_id": str(timbal_id),
            "default_quantity": "0",
            "is_active": "1",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Inga personer kvar? Ta bort kostbehovet från avdelningen." in html
    assert DepartmentRequirementGroupsRepo().list_for_department(dep["id"]) == []

    from core.department_requirement_group_weekview_projection import build_department_requirement_group_weekview_projection

    projection_active = build_department_requirement_group_weekview_projection(
        tenant_id=None,
        site_id=site["id"],
        department_id=dep["id"],
        service_date=date(2026, 10, 8),
        meal_key="lunch",
    )
    assert len(projection_active.needs) == 0
def test_edit_form_shows_unresolved_requirement_group_and_requires_primary(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement group unresolved UI site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Unresolved",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")
    laktosfri_id = DietTypesRepo().create(site_id=site["id"], name="Laktosfri", default_select=False, semantics="atomic")

    DepartmentsRepo().upsert_department_diet_defaults(
        dep["id"],
        expected_version=0,
        items=[
            {"diet_type_id": timbal_id, "default_count": 1},
            {"diet_type_id": glutenfri_id, "default_count": 1},
        ],
    )

    unresolved = DepartmentRequirementGroupsRepo().create_group(
        dep["id"],
        1,
        [timbal_id, laktosfri_id],
        label="Legacy unresolved",
        primary_requirement_id=None,
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    page = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Laktosfri" in html

    resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data={
            "group_id": str(unresolved["id"]),
            "primary_requirement_id": str(timbal_id),
            "modifier_requirement_ids": [str(laktosfri_id)],
            "default_quantity": "1",
            "is_active": "1",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200
    reread = DepartmentRequirementGroupsRepo().get_group(str(unresolved["id"]))
    assert reread is not None
    assert reread["primary_requirement_id"] == timbal_id
    assert {item["dietary_type_id"] for item in reread["requirements"]} == {timbal_id, laktosfri_id}


def test_edit_form_renders_unified_variation_entrypoints_for_registered_needs(client_admin):
    site, _ = SitesRepo().create_site(f"Weekday UI render site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Weekday Render",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")

    DepartmentsRepo().upsert_department_diet_defaults(
        dep["id"],
        expected_version=0,
        items=[
            {"diet_type_id": timbal_id, "default_count": 1},
            {"diet_type_id": glutenfri_id, "default_count": 1},
        ],
    )

    group = DepartmentRequirementGroupsRepo().create_group(
        dep["id"],
        2,
        [timbal_id, glutenfri_id],
        label="Timbal + Glutenfri",
        primary_requirement_id=timbal_id,
    )
    weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
    weekday_repo.set_override(group["id"], 4, "lunch", 1)
    weekday_repo.set_override(group["id"], 4, "dinner", 0)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    page = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert html.count("Hantera variation") == 1
    assert html.count('+ Lägg till kostbehov') >= 2
    assert "Varierar" in html
    assert re.search(r'name="need_day_[^"]+_1_lunch"[^>]*value="2"', html)
    assert re.search(r'name="need_day_[^"]+_4_lunch"[^>]*value="1"', html)
    assert re.search(r'name="need_day_[^"]+_4_dinner"[^>]*value="0"', html)
    assert 'name="weekday_quantity_' not in html


def test_edit_form_saves_weekday_quantities_and_resets_without_touching_legacy_tables(client_admin):
    site, _ = SitesRepo().create_site(f"Weekday UI save site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Weekday Save",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")

    dept_repo = DepartmentsRepo()
    dept_repo.upsert_department_diet_defaults(
        dep["id"],
        expected_version=0,
        items=[
            {"diet_type_id": timbal_id, "default_count": 1},
            {"diet_type_id": glutenfri_id, "default_count": 1},
        ],
    )
    legacy_defaults_before = DietDefaultsRepo().list_for_department(dep["id"])
    DepartmentDietOverridesRepo().replace_for_department_diet(dep["id"], timbal_id, [{"day": 4, "meal": "lunch", "count": 9}])
    legacy_overrides_before = DepartmentDietOverridesRepo().list_for_department(dep["id"])

    group = DepartmentRequirementGroupsRepo().create_group(
        dep["id"],
        2,
        [timbal_id, glutenfri_id],
        label="Timbal + Glutenfri",
        primary_requirement_id=timbal_id,
    )
    exact_repo = DepartmentRequirementGroupServiceOverridesRepo()
    exact_repo.set_override(group["id"], date(2026, 9, 10), "lunch", 5)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    create_resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data=_build_weekday_override_payload(
            group_id=group["id"],
            primary_requirement_id=timbal_id,
            default_quantity=2,
            overrides={
                (4, "lunch"): 1,
                (4, "dinner"): 0,
            },
        ),
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert create_resp.status_code == 200
    overrides = DepartmentRequirementGroupWeekdayOverridesRepo().list_for_group(group["id"])
    assert overrides == [
        {"group_id": group["id"], "weekday": 4, "meal_key": "dinner", "quantity": 0},
        {"group_id": group["id"], "weekday": 4, "meal_key": "lunch", "quantity": 1},
    ]
    assert exact_repo.resolve_effective_quantity(group["id"], date(2026, 9, 10), "lunch") == 5
    assert DietDefaultsRepo().list_for_department(dep["id"]) == legacy_defaults_before
    assert DepartmentDietOverridesRepo().list_for_department(dep["id"]) == legacy_overrides_before

    reset_resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data=_build_weekday_override_payload(
            group_id=group["id"],
            primary_requirement_id=timbal_id,
            default_quantity=2,
            overrides={
                (4, "lunch"): 2,
                (4, "dinner"): None,
            },
        ),
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert reset_resp.status_code == 200
    overrides_after_reset = DepartmentRequirementGroupWeekdayOverridesRepo().list_for_group(group["id"])
    assert overrides_after_reset == []
    assert exact_repo.resolve_effective_quantity(group["id"], date(2026, 9, 10), "lunch") == 5
    assert DietDefaultsRepo().list_for_department(dep["id"]) == legacy_defaults_before
    assert DepartmentDietOverridesRepo().list_for_department(dep["id"]) == legacy_overrides_before


def test_edit_form_rejects_cross_department_and_negative_weekday_quantities(client_admin):
    site, _ = SitesRepo().create_site(f"Weekday UI validation site {uuid.uuid4()}")
    dep_a, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd A",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    dep_b, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd B",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_a = DietTypesRepo().create(site_id=site["id"], name="Timbal A", default_select=False, semantics="atomic")
    timbal_b = DietTypesRepo().create(site_id=site["id"], name="Timbal B", default_select=False, semantics="atomic")

    DepartmentsRepo().upsert_department_diet_defaults(
        dep_a["id"],
        expected_version=0,
        items=[{"diet_type_id": timbal_a, "default_count": 1}],
    )
    DepartmentsRepo().upsert_department_diet_defaults(
        dep_b["id"],
        expected_version=0,
        items=[{"diet_type_id": timbal_b, "default_count": 1}],
    )

    group_a = DepartmentRequirementGroupsRepo().create_group(
        dep_a["id"],
        2,
        [timbal_a],
        label="A",
        primary_requirement_id=timbal_a,
    )
    group_b = DepartmentRequirementGroupsRepo().create_group(
        dep_b["id"],
        2,
        [timbal_b],
        label="B",
        primary_requirement_id=timbal_b,
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    negative_resp = client_admin.post(
        f"/ui/admin/departments/{dep_a['id']}/requirement-groups",
        data=_build_weekday_override_payload(
            group_id=group_a["id"],
            primary_requirement_id=timbal_a,
            default_quantity=2,
            overrides={(4, "lunch"): -1},
        ),
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert negative_resp.status_code == 200
    assert "Antal måste vara 0 eller högre." in negative_resp.get_data(as_text=True)
    assert DepartmentRequirementGroupsRepo().get_group(group_a["id"]) is not None
    assert DepartmentRequirementGroupWeekdayOverridesRepo().list_for_group(group_a["id"]) == []

    forbidden_resp = client_admin.post(
        f"/ui/admin/departments/{dep_a['id']}/requirement-groups",
        data=_build_weekday_override_payload(
            group_id=group_b["id"],
            primary_requirement_id=timbal_b,
            default_quantity=2,
            overrides={(4, "lunch"): 1},
        ),
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert forbidden_resp.status_code == 200
    assert "Avdelningen hittades inte för vald site." in forbidden_resp.get_data(as_text=True)
    assert DepartmentRequirementGroupWeekdayOverridesRepo().list_for_group(group_b["id"]) == []
