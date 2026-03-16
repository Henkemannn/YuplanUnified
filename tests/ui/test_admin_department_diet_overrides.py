from __future__ import annotations

import uuid

from sqlalchemy import text

from core import admin_repo as admin_repo_module
from core.admin_repo import DepartmentDietOverridesRepo, DepartmentsRepo, DietTypesRepo, SitesRepo
from core.db import get_session


def _h(role: str) -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_admin_diet_overrides_save_diff_only_and_reset(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Diet override site {uuid.uuid4()}")
    dep, dep_v = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Diet Override",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    diet_id = DietTypesRepo().create(site_id=site["id"], name="Glutenfri", default_select=False)
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
    diet_id = DietTypesRepo().create(site_id=site["id"], name="Laktosfri", default_select=False)
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
