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
    mos_id = addon_repo.create_if_missing("Mos", site_id=site["id"], addon_family="mos")
    sallad_id = addon_repo.create_if_missing("Sallad", site_id=site["id"], addon_family="sallad")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]

    r_save = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/edit/service-addons",
        headers=_h("admin"),
        data={
            "service_addon_id[]": [mos_id, sallad_id],
            "service_addon_new_name[]": ["", ""],
            "service_addon_family[]": ["mos", "sallad"],
            "service_addon_lunch_count[]": ["4", "0"],
            "service_addon_dinner_count[]": ["", "2"],
            "service_addon_note[]": ["Aldrig tomat", ""],
        },
    )
    assert r_save.status_code in (302, 303)

    rows = DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"])
    assert len(rows) == 2

    r_get = client_admin.get(f"/ui/admin/departments/{dep['id']}/edit", headers=_h("admin"))
    assert r_get.status_code == 200
    html = r_get.get_data(as_text=True)
    assert "Serveringstillägg" in html
    assert "Familj" in html
    assert "Aldrig tomat" in html
    assert "value=\"4\"" in html

    r_remove = client_admin.post(
        f"/ui/admin/departments/{dep['id']}/edit/service-addons",
        headers=_h("admin"),
        data={
            "service_addon_id[]": [mos_id],
            "service_addon_new_name[]": [""],
            "service_addon_family[]": ["mos"],
            "service_addon_lunch_count[]": ["0"],
            "service_addon_dinner_count[]": ["0"],
            "service_addon_note[]": [""],
        },
    )
    assert r_remove.status_code in (302, 303)
    assert DepartmentServiceAddonsRepo().list_for_department(dep["id"], site_id=site["id"]) == []


def test_admin_department_service_addons_are_site_isolated(app_session, client_admin):
    site_a, _ = SitesRepo().create_site(f"Service addon site A {uuid.uuid4()}")
    site_b, _ = SitesRepo().create_site(f"Service addon site B {uuid.uuid4()}")

    dep_a, _ = DepartmentsRepo().create_department(
        site_id=site_a["id"],
        name="Avd Site A",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    _dep_b, _ = DepartmentsRepo().create_department(
        site_id=site_b["id"],
        name="Avd Site B",
        resident_count_mode="fixed",
        resident_count_fixed=11,
    )

    addon_repo = ServiceAddonsRepo()
    addon_a = addon_repo.create_if_missing("A-Mos", site_id=site_a["id"], addon_family="mos")
    addon_b = addon_repo.create_if_missing("B-Sallad", site_id=site_b["id"], addon_family="sallad")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_a["id"]

    r_get = client_admin.get(f"/ui/admin/departments/{dep_a['id']}/edit", headers=_h("admin"))
    assert r_get.status_code == 200
    html = r_get.get_data(as_text=True)
    assert "A-Mos" in html
    assert "B-Sallad" not in html

    # Cross-site write must be blocked by backend guard.
    r_save = client_admin.post(
        f"/ui/admin/departments/{dep_a['id']}/edit/service-addons",
        headers=_h("admin"),
        data={
            "service_addon_id[]": [addon_b],
            "service_addon_new_name[]": [""],
            "service_addon_family[]": ["sallad"],
            "service_addon_lunch_count[]": ["3"],
            "service_addon_dinner_count[]": ["0"],
            "service_addon_note[]": [""],
        },
    )
    assert r_save.status_code in (302, 303)
    assert DepartmentServiceAddonsRepo().list_for_department(dep_a["id"], site_id=site_a["id"]) == []
