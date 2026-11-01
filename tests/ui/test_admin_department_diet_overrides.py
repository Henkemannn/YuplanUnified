from __future__ import annotations

import uuid

from sqlalchemy import text

from core import admin_repo as admin_repo_module
from core.admin_repo import DepartmentDietOverridesRepo, DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo
from core.db import get_session


def _h(role: str) -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _canonical_diet_id(site_id: str, name: str, *, default_select: bool) -> int:
    row = next(row for row in DietTypesRepo().list_all(site_id=site_id) if row["name"] == name)
    assert row["semantics"] == "atomic"
    assert row["requirement_key"]
    if bool(row["default_select"]) != default_select:
        DietTypesRepo().update(int(row["id"]), default_select=default_select)
        row = next(row for row in DietTypesRepo().list_all(site_id=site_id) if row["name"] == name)
    assert bool(row["default_select"]) is default_select
    return int(row["id"])


def test_admin_diet_overrides_save_diff_only_and_reset(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Diet override site {uuid.uuid4()}")
    dep, dep_v = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Diet Override",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    diet_id = _canonical_diet_id(site["id"], "Glutenfri", default_select=False)
    DepartmentsRepo().upsert_department_diet_defaults(
        dept_id=dep["id"],
        expected_version=dep_v,
        items=[{"diet_type_id": str(diet_id), "default_count": 4}],
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    r_get = client_admin.get(
        f"/ui/admin/departments/{dep['id']}/diet-overrides?diet_type_id={diet_id}",
        headers=_h("admin"),
    )
    assert r_get.status_code == 200
    data_get = r_get.get_json() or {}
    assert int(data_get.get("base_count") or 0) == 4
    assert data_get.get("overrides") == []

    r_save = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/diet-overrides",
        headers=_h("admin"),
        json={
            "diet_type_id": str(diet_id),
            "entries": [
                {"day": 1, "meal": "lunch", "count": 4},
                {"day": 1, "meal": "dinner", "count": 6},
                {"day": 2, "meal": "lunch", "count": 2},
            ],
        },
    )
    assert r_save.status_code == 200
    data_save = r_save.get_json() or {}
    assert bool(data_save.get("ok")) is True
    assert int(data_save.get("saved") or 0) == 2

    rows = DepartmentDietOverridesRepo().list_for_department_diet(dep["id"], str(diet_id))
    assert len(rows) == 2

    r_reset = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/diet-overrides/reset",
        headers=_h("admin"),
        json={"diet_type_id": str(diet_id)},
    )
    assert r_reset.status_code == 200
    data_reset = r_reset.get_json() or {}
    assert bool(data_reset.get("ok")) is True
    assert DepartmentDietOverridesRepo().list_for_department_diet(dep["id"], str(diet_id)) == []


def test_admin_diet_overrides_get_accepts_explicit_site_id_fallback(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Diet override fallback site {uuid.uuid4()}")
    dep, dep_v = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Diet Override Site Fallback",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    diet_id = _canonical_diet_id(site["id"], "Laktosfri", default_select=False)
    DepartmentsRepo().upsert_department_diet_defaults(
        dept_id=dep["id"],
        expected_version=dep_v,
        items=[{"diet_type_id": str(diet_id), "default_count": 2}],
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = "some-other-site"

    r_get = client_admin.get(
        f"/ui/admin/departments/{dep['id']}/diet-overrides?diet_type_id={diet_id}&site_id={site['id']}",
        headers=_h("admin"),
    )
    assert r_get.status_code == 200
    data_get = r_get.get_json() or {}
    assert int(data_get.get("base_count") or 0) == 2


def test_department_diet_overrides_repo_tolerates_missing_table(app_session, monkeypatch):
    db = get_session()
    try:
        db.execute(text("DROP TABLE IF EXISTS department_diet_overrides"))
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        admin_repo_module,
        "_ensure_department_diet_overrides_table",
        lambda _db: None,
    )

    repo = DepartmentDietOverridesRepo()
    assert repo.list_for_department_diet("dept-x", "35") == []
    repo.replace_for_department_diet(
        dept_id="dept-x",
        diet_type_id="35",
        items=[{"day": 1, "meal": "lunch", "count": 3}],
    )


def test_edit_form_marks_diet_override_button_when_overrides_exist(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Diet override highlight site {uuid.uuid4()}")
    dep, dep_v = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Diet Override Highlight",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    diet_id = _canonical_diet_id(site["id"], "Timbal", default_select=False)
    DepartmentsRepo().upsert_department_diet_defaults(
        dept_id=dep["id"],
        expected_version=dep_v,
        items=[{"diet_type_id": str(diet_id), "default_count": 2}],
    )
    group = DepartmentRequirementGroupsRepo().create_group(
        department_id=dep["id"],
        default_quantity=2,
        requirement_ids=[diet_id],
        label="Timbal",
        primary_requirement_id=diet_id,
    )
    weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
    weekday_repo.set_override(group["id"], 1, "lunch", 3)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    resp = client_admin.get(
        f"/ui/admin/departments/{dep['id']}/edit",
        headers=_h("admin"),
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    reread_group = DepartmentRequirementGroupsRepo().get_group(group["id"])
    assert reread_group is not None
    assert reread_group["department_id"] == dep["id"]
    assert {row["dietary_type_id"] for row in reread_group["requirements"]} == {diet_id}
    assert weekday_repo.list_for_group(group["id"]) == [
        {
            "group_id": group["id"],
            "weekday": 1,
            "meal_key": "lunch",
            "quantity": 3,
        }
    ]
    assert "Hantera variation" in html
    assert "Varierar" in html
    assert f'name="need_day_{group["id"]}_1_lunch"' in html
    assert f'name="need_day_{group["id"]}_1_lunch" value="3"' in html
