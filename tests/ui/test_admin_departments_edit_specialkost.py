import uuid
import re
import pytest
from datetime import date

from core.db import get_session
from core.admin_repo import DietDefaultsRepo, DepartmentDietOverridesRepo, DietTypesRepo, DepartmentsRepo, SitesRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo
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


def test_edit_form_renders_weekday_quantity_controls_for_registered_needs(client_admin):
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
    assert re.search(rf'name="weekday_quantity_{re.escape(group["id"])}_1_lunch"[^>]*value="2"', html)
    assert re.search(rf'name="weekday_quantity_{re.escape(group["id"])}_4_lunch"[^>]*value="1"', html)
    assert re.search(rf'name="weekday_quantity_{re.escape(group["id"])}_4_dinner"[^>]*value="0"', html)


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
