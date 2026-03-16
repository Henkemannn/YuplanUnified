from __future__ import annotations

import uuid

from core.admin_repo import (
    DepartmentServiceAddonsRepo,
    DepartmentsRepo,
    ServiceAddonsRepo,
    SitesRepo,
)


def test_service_addons_totals_aggregate_and_hide_zero_and_include_note(app_session):
    site, _ = SitesRepo().create_site(f"Kitchen addon totals {uuid.uuid4()}")
    dep_a, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Lindgarden A",
        resident_count_mode="fixed",
        resident_count_fixed=8,
    )
    dep_b, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Lindgarden B",
        resident_count_mode="fixed",
        resident_count_fixed=9,
    )

    addon_repo = ServiceAddonsRepo()
    mos_id = addon_repo.create_if_missing("Mos", addon_family="mos")
    sallad_id = addon_repo.create_if_missing("Sallad", addon_family="sallad")

    dep_repo = DepartmentServiceAddonsRepo()
    dep_repo.replace_for_department(
        dep_a["id"],
        [
            {"addon_id": mos_id, "lunch_count": 4, "dinner_count": None, "note": "Aldrig tomat"},
            {"addon_id": sallad_id, "lunch_count": 0, "dinner_count": 3, "note": ""},
        ],
    )
    dep_repo.replace_for_department(
        dep_b["id"],
        [
            {"addon_id": mos_id, "lunch_count": 3, "dinner_count": 0, "note": ""},
            {"addon_id": sallad_id, "lunch_count": 0, "dinner_count": 0, "note": ""},
        ],
    )

    lunch = dep_repo.list_totals_for_site_meal(site["id"], "lunch")
    assert len(lunch) == 1
    assert lunch[0]["addon_name"] == "Mos"
    assert lunch[0]["addon_family"] == "mos"
    assert int(lunch[0]["total_count"]) == 7
    notes = {d["department_name"]: d.get("note") for d in lunch[0]["departments"]}
    assert notes.get("Lindgarden A") == "Aldrig tomat"

    dinner = dep_repo.list_totals_for_site_meal(site["id"], "dinner")
    assert len(dinner) == 1
    assert dinner[0]["addon_name"] == "Sallad"
    assert dinner[0]["addon_family"] == "sallad"
    assert int(dinner[0]["total_count"]) == 3
    dep_names = {d["department_name"] for d in dinner[0]["departments"]}
    assert dep_names == {"Lindgarden A"}
