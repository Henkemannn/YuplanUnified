from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from core.admin_repo import (
    DepartmentServiceAddonsRepo,
    DepartmentsRepo,
    ServiceAddonDataIntegrityError,
    ServiceAddonsRepo,
    SitesRepo,
    _ensure_service_addons_tables,
)
from core.residents_schedule_repo import ResidentsScheduleRepo
from core.service_addon_contract import resolve_service_addon_quantity


def _row_by_name(rows: list[dict], addon_name: str) -> dict:
    for row in rows:
        if row["addon_name"] == addon_name:
            return row
    raise AssertionError(f"missing addon row: {addon_name}")


def test_service_addon_scope_mode_and_whole_department_resolution(app_session):
    site, _ = SitesRepo().create_site(f"Service addon contract {uuid.uuid4()}")

    fixed_dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Fixed",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    schedule_dep, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Schedule",
        resident_count_mode="per_day_meal",
        resident_count_fixed=0,
    )

    ResidentsScheduleRepo().upsert_items(
        schedule_dep["id"],
        40,
        [
            {"weekday": 2, "meal": "lunch", "count": 7},
            {"weekday": 2, "meal": "dinner", "count": 9},
        ],
    )

    addon_repo = ServiceAddonsRepo()
    whole_fixed_id = addon_repo.create_if_missing("Hela avdelningen fast", site_id=site["id"], addon_family="mos")
    whole_schedule_id = addon_repo.create_if_missing("Hela avdelningen schema", site_id=site["id"], addon_family="sallad")
    all_services_id = addon_repo.create_if_missing("Alla serveringar", site_id=site["id"], addon_family="ovrigt")
    lunch_only_id = addon_repo.create_if_missing("Lunch endast", site_id=site["id"], addon_family="ovrigt")
    dinner_only_id = addon_repo.create_if_missing("Kväll endast", site_id=site["id"], addon_family="ovrigt")

    dep_repo = DepartmentServiceAddonsRepo()
    dep_repo.replace_for_department(
        fixed_dep["id"],
        [
            {
                "addon_id": whole_fixed_id,
                "service_scope": "all_services",
                "quantity_mode": "whole_department",
                "lunch_count": None,
                "dinner_count": None,
                "note": "Dynamisk fast avdelning",
            },
            {
                "addon_id": all_services_id,
                "service_scope": "all_services",
                "quantity_mode": "custom",
                "lunch_count": 4,
                "dinner_count": 6,
                "note": "Skiljer sig mellan måltider",
            },
            {
                "addon_id": lunch_only_id,
                "service_scope": "lunch",
                "quantity_mode": "custom",
                "lunch_count": 3,
                "dinner_count": None,
                "note": "",
            },
            {
                "addon_id": dinner_only_id,
                "service_scope": "dinner",
                "quantity_mode": "custom",
                "lunch_count": None,
                "dinner_count": 2,
                "note": "",
            },
        ],
        site_id=site["id"],
    )
    dep_repo.replace_for_department(
        schedule_dep["id"],
        [
            {
                "addon_id": whole_schedule_id,
                "service_scope": "all_services",
                "quantity_mode": "whole_department",
                "lunch_count": None,
                "dinner_count": None,
                "note": "Dynamisk daglig avdelning",
            }
        ],
        site_id=site["id"],
    )

    fixed_rows = dep_repo.list_for_department(fixed_dep["id"], site_id=site["id"])
    fixed_whole = _row_by_name(fixed_rows, "Hela avdelningen fast")
    assert fixed_whole["service_scope"] == "all_services"
    assert fixed_whole["quantity_mode"] == "whole_department"
    assert fixed_whole["lunch_count"] is None
    assert fixed_whole["dinner_count"] is None
    assert _row_by_name(fixed_rows, "Alla serveringar")["service_scope"] == "all_services"
    assert _row_by_name(fixed_rows, "Lunch endast")["service_scope"] == "lunch"
    assert _row_by_name(fixed_rows, "Kväll endast")["service_scope"] == "dinner"

    assert (
        resolve_service_addon_quantity(
            fixed_whole,
            meal="lunch",
            year=2026,
            week=40,
            weekday=2,
        )
        == 10
    )


    assert (
        resolve_service_addon_quantity(
            fixed_whole,
            meal="dinner",
            year=2026,
            week=40,
            weekday=2,
        )
        == 10
    )
    assert (
        resolve_service_addon_quantity(
            _row_by_name(fixed_rows, "Alla serveringar"),
            meal="lunch",
            year=2026,
            week=40,
            weekday=2,
        )
        == 4
    )
    assert (
        resolve_service_addon_quantity(
            _row_by_name(fixed_rows, "Alla serveringar"),
            meal="dinner",
            year=2026,
            week=40,
            weekday=2,
        )
        == 6
    )
    assert (
        resolve_service_addon_quantity(
            _row_by_name(fixed_rows, "Lunch endast"),
            meal="dinner",
            year=2026,
            week=40,
            weekday=2,
        )
        == 0
    )
    assert (
        resolve_service_addon_quantity(
            _row_by_name(fixed_rows, "Kväll endast"),
            meal="lunch",
            year=2026,
            week=40,
            weekday=2,
        )
        == 0
    )

    schedule_rows = dep_repo.list_for_department(schedule_dep["id"], site_id=site["id"])
    schedule_whole = _row_by_name(schedule_rows, "Hela avdelningen schema")
    assert (
        resolve_service_addon_quantity(
            schedule_whole,
            meal="lunch",
            year=2026,
            week=40,
            weekday=2,
        )
        == 7
    )
    assert (
        resolve_service_addon_quantity(
            schedule_whole,
            meal="dinner",
            year=2026,
            week=40,
            weekday=2,
        )
        == 9
    )

    lunch_rows = dep_repo.list_totals_for_site_meal_with_context(site["id"], "lunch", year=2026, week=40, weekday=2)
    lunch_counts = {row["addon_name"]: int(row["total_count"]) for row in lunch_rows}
    assert lunch_counts == {
        "Hela avdelningen fast": 10,
        "Hela avdelningen schema": 7,
        "Alla serveringar": 4,
        "Lunch endast": 3,
    }

    dinner_rows = dep_repo.list_totals_for_site_meal_with_context(site["id"], "dinner", year=2026, week=40, weekday=2)
    dinner_counts = {row["addon_name"]: int(row["total_count"]) for row in dinner_rows}
    assert dinner_counts == {
        "Hela avdelningen fast": 10,
        "Hela avdelningen schema": 9,
        "Alla serveringar": 6,
        "Kväll endast": 2,
    }


def test_invalid_legacy_scope_is_reported_with_row_context(app_session):
    from core.db import get_session

    site_id = f"site-invalid-{uuid.uuid4()}"
    department_id = f"dept-invalid-{uuid.uuid4()}"
    row_id = f"row-invalid-{uuid.uuid4()}"
    db = get_session()
    try:
        _ensure_service_addons_tables(db)
        db.execute(
            text(
                "INSERT INTO sites(id, tenant_id, name) VALUES(:site, 1, 'Invalid scope site')"
            ),
            {"site": site_id},
        )
        db.execute(
            text(
                "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) "
                "VALUES(:department, :site, 'Invalid scope department', 'fixed', 10)"
            ),
            {"department": department_id, "site": site_id},
        )
        db.execute(
            text(
                "INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at) "
                "VALUES(:addon, :site, 'Invalid scope addon', 'ovrigt', 1, CURRENT_TIMESTAMP)"
            ),
            {"addon": f"addon-{uuid.uuid4()}", "site": site_id},
        )
        addon_id = db.execute(
            text("SELECT id FROM service_addons WHERE site_id=:site ORDER BY created_at DESC LIMIT 1"),
            {"site": site_id},
        ).scalar_one()
        db.execute(
            text(
                "INSERT INTO department_service_addons("
                "id, department_id, addon_id, service_scope, quantity_mode, lunch_count, dinner_count"
                ") VALUES(:row, :department, :addon, 'breakfast', 'custom', 5, NULL)"
            ),
            {"row": row_id, "department": department_id, "addon": addon_id},
        )
        db.commit()
    finally:
        db.close()

    with pytest.raises(ServiceAddonDataIntegrityError) as exc_info:
        ServiceAddonsRepo().list_active(site_id)

    error = exc_info.value
    assert error.row_id == row_id
    assert error.department_id == department_id
    assert error.site_id == site_id
    assert error.service_scope == "breakfast"

    cleanup = get_session()
    try:
        cleanup.execute(
            text("DELETE FROM department_service_addons WHERE id=:id"),
            {"id": row_id},
        )
        cleanup.execute(
            text("DELETE FROM service_addons WHERE site_id=:site"),
            {"site": site_id},
        )
        cleanup.execute(
            text("DELETE FROM departments WHERE id=:department"),
            {"department": department_id},
        )
        cleanup.execute(text("DELETE FROM sites WHERE id=:site"), {"site": site_id})
        cleanup.commit()
    finally:
        cleanup.close()
