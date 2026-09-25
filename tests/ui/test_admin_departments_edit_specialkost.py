import uuid
import re
import pytest

from core.db import get_session
from core.admin_repo import DietDefaultsRepo, DietTypesRepo, DepartmentsRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from sqlalchemy import text

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
    assert "Specialkost (antal på avdelningen)" in html
    assert "app-shell__env-badge" in html
    assert '<div class="app-shell__card-meta">Vecka ' not in html

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
        "version": "0",
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
    assert "specialkost-edit-group" in html
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
    assert "Registrerade behov" in html
    create_select = re.search(r'<select id="new_primary_requirement_id"[^>]*>(.*?)</select>', html, re.S)
    assert create_select is not None
    create_options = create_select.group(1)
    assert "Timbal" in create_options
    assert "Glutenfri" in create_options
    assert "Flytande kost" in create_options
    assert "Laktosfri" not in create_options

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
    assert {item["dietary_type_id"] for item in reread["requirements"]} == {timbal_id, glutenfri_id}

    page = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Registrerade behov" in html
    assert "Timbal" in html
    assert "Glutenfri" in html
    assert "Ytterligare avvikelser" in html
    assert DietDefaultsRepo().list_for_department(dep["id"]) == defaults_before
    assert len(DietTypesRepo().list_all(site_id=site["id"])) == diet_count_before


def test_edit_form_rejects_unconfigured_requirement_in_create_flow(client_admin):
    site, _ = SitesRepo().create_site(f"Requirement group rejection site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Reject",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = DietTypesRepo().create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")
    laktosfri_id = DietTypesRepo().create(site_id=site["id"], name="Laktosfri", default_select=False, semantics="atomic")
    DietTypesRepo().create(site_id=site["id"], name="Flytande kost", default_select=False, semantics="atomic")

    DepartmentsRepo().upsert_department_diet_defaults(
        dep["id"],
        expected_version=0,
        items=[
            {"diet_type_id": timbal_id, "default_count": 1},
            {"diet_type_id": glutenfri_id, "default_count": 1},
        ],
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data={
            "primary_requirement_id": str(laktosfri_id),
            "default_quantity": "1",
            "is_active": "1",
        },
        follow_redirects=True,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Välj bara specialkost som redan är kopplad till avdelningen." in html
    assert DepartmentRequirementGroupsRepo().list_for_department(dep["id"]) == []
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
    assert "Huvudsaklig specialkost behöver anges" in html
    assert "Laktosfri" in html

    resp = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/requirement-groups",
        data={
            "group_id": str(unresolved["id"]),
            "primary_requirement_id": str(timbal_id),
            "default_quantity": "1",
            "modifier_requirement_ids": [str(laktosfri_id)],
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
