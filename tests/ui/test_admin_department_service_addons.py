from __future__ import annotations

import uuid

from core.admin_repo import (
    DepartmentServiceAddonsRepo,
    DepartmentsRepo,
    ServiceAddonsRepo,
    SitesRepo,
)


def _h(role: str) -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_admin_department_service_addons_save_load_remove(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Service addon site {uuid.uuid4()}")
    dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Service",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )

    addon_repo = ServiceAddonsRepo()
    mos_id = addon_repo.create_if_missing("Mos")
    sallad_id = addon_repo.create_if_missing("Sallad")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    r_save = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/edit/service-addons",
        headers=_h("admin"),
        data={
            "service_addon_id[]": [mos_id, sallad_id],
            "service_addon_new_name[]": ["", ""],
            "service_addon_lunch_count[]": ["4", "0"],
            "service_addon_dinner_count[]": ["", "2"],
            "service_addon_note[]": ["Aldrig tomat", ""],
        },
    )
    assert r_save.status_code in (302, 303)

    rows = DepartmentServiceAddonsRepo().list_for_department(dep["id"])
    assert len(rows) == 2

    r_get = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers=_h("admin"))
    assert r_get.status_code == 200
    html = r_get.get_data(as_text=True)
    assert "Serveringstillägg" in html
    assert "Aldrig tomat" in html
    assert "value=\"4\"" in html

    r_remove = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/edit/service-addons",
        headers=_h("admin"),
        data={
            "service_addon_id[]": [mos_id],
            "service_addon_new_name[]": [""],
            "service_addon_lunch_count[]": ["0"],
            "service_addon_dinner_count[]": ["0"],
            "service_addon_note[]": [""],
        },
    )
    assert r_remove.status_code in (302, 303)
    assert DepartmentServiceAddonsRepo().list_for_department(dep["id"]) == []
