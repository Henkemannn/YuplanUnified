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


def test_invalid_legacy_scope_is_reported_with_row_context(app_session, request):
    from core.db import get_session

    site_id = f"site-invalid-{uuid.uuid4()}"
    department_id = f"dept-invalid-{uuid.uuid4()}"
    row_id = f"row-invalid-{uuid.uuid4()}"
    addon_id = f"addon-invalid-{uuid.uuid4()}"

    def cleanup_invalid_rows() -> None:
        cleanup = get_session()
        try:
            cleanup.execute(
                text("DELETE FROM department_service_addons WHERE id=:id"),
                {"id": row_id},
            )
            cleanup.execute(
                text("DELETE FROM service_addons WHERE id=:id"),
                {"id": addon_id},
            )
            cleanup.execute(
                text("DELETE FROM departments WHERE id=:id"),
                {"id": department_id},
            )
            cleanup.execute(text("DELETE FROM sites WHERE id=:id"), {"id": site_id})
            cleanup.commit()
        finally:
            cleanup.close()

    request.addfinalizer(cleanup_invalid_rows)
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
            {"addon": addon_id, "site": site_id},
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


def test_legacy_null_site_and_scope_are_scoped_without_ambiguous_repair(app_session, request):
    from core.db import get_session

    site_a = f"site-legacy-a-{uuid.uuid4()}"
    site_b = f"site-legacy-b-{uuid.uuid4()}"
    department_a = f"dept-legacy-a-{uuid.uuid4()}"
    department_b = f"dept-legacy-b-{uuid.uuid4()}"
    addon_unique = f"addon-legacy-unique-{uuid.uuid4()}"
    addon_ambiguous = f"addon-legacy-ambiguous-{uuid.uuid4()}"
    addon_null_scope = f"addon-legacy-null-scope-{uuid.uuid4()}"

    def cleanup_legacy_rows() -> None:
        cleanup = get_session()
        try:
            cleanup.execute(
                text(
                    "DELETE FROM department_service_addons "
                    "WHERE department_id IN (:department_a, :department_b)"
                ),
                {"department_a": department_a, "department_b": department_b},
            )
            cleanup.execute(
                text(
                    "DELETE FROM service_addons "
                    "WHERE id IN (:unique, :ambiguous, :null_scope)"
                ),
                {
                    "unique": addon_unique,
                    "ambiguous": addon_ambiguous,
                    "null_scope": addon_null_scope,
                },
            )
            cleanup.execute(
                text("DELETE FROM departments WHERE id IN (:department_a, :department_b)"),
                {"department_a": department_a, "department_b": department_b},
            )
            cleanup.execute(
                text("DELETE FROM sites WHERE id IN (:site_a, :site_b)"),
                {"site_a": site_a, "site_b": site_b},
            )
            cleanup.commit()
        finally:
            cleanup.close()

    request.addfinalizer(cleanup_legacy_rows)
    db = get_session()
    try:
        _ensure_service_addons_tables(db)
        db.execute(
            text(
                "INSERT INTO sites(id, tenant_id, name) VALUES(:site_a, 1, 'Legacy A'), (:site_b, 1, 'Legacy B')"
            ),
            {"site_a": site_a, "site_b": site_b},
        )
        db.execute(
            text(
                "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) "
                "VALUES(:department_a, :site_a, 'Legacy Dept A', 'fixed', 10), "
                "(:department_b, :site_b, 'Legacy Dept B', 'fixed', 10)"
            ),
            {
                "department_a": department_a,
                "department_b": department_b,
                "site_a": site_a,
                "site_b": site_b,
            },
        )
        db.execute(
            text(
                "INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at) "
                "VALUES(:unique, NULL, 'Legacy unique', 'ovrigt', 1, CURRENT_TIMESTAMP), "
                "(:ambiguous, NULL, 'Legacy ambiguous', 'ovrigt', 1, CURRENT_TIMESTAMP), "
                "(:null_scope, :site_a, 'Legacy null scope', 'ovrigt', 1, CURRENT_TIMESTAMP)"
            ),
            {
                "unique": addon_unique,
                "ambiguous": addon_ambiguous,
                "null_scope": addon_null_scope,
                "site_a": site_a,
            },
        )
        db.execute(
            text(
                "INSERT INTO department_service_addons("
                "id, department_id, addon_id, service_scope, quantity_mode, lunch_count, dinner_count"
                ") VALUES"
                "(:unique_row, :department_a, :unique, 'lunch', 'custom', 2, NULL), "
                "(:ambiguous_a, :department_a, :ambiguous, 'lunch', 'custom', 2, NULL), "
                "(:ambiguous_b, :department_b, :ambiguous, 'dinner', 'custom', NULL, 3), "
                "(:null_scope_row, :department_a, :null_scope, NULL, 'custom', 4, NULL)"
            ),
            {
                "unique_row": f"row-unique-{uuid.uuid4()}",
                "ambiguous_a": f"row-ambiguous-a-{uuid.uuid4()}",
                "ambiguous_b": f"row-ambiguous-b-{uuid.uuid4()}",
                "null_scope_row": f"row-null-scope-{uuid.uuid4()}",
                "department_a": department_a,
                "department_b": department_b,
                "unique": addon_unique,
                "ambiguous": addon_ambiguous,
                "null_scope": addon_null_scope,
            },
        )
        db.commit()
    finally:
        db.close()

    rows = ServiceAddonsRepo().list_active(site_a)
    names = {row["name"] for row in rows}
    assert "Legacy unique" in names
    assert "Legacy ambiguous" not in names, names

    scoped_rows = DepartmentServiceAddonsRepo().list_for_department(department_a, site_id=site_a)
    null_scope_row = _row_by_name(scoped_rows, "Legacy null scope")
    assert null_scope_row["service_scope"] == "lunch"
    assert null_scope_row["lunch_count"] == 4

    verification = get_session()
    try:
        assert verification.execute(
            text("SELECT site_id FROM service_addons WHERE id=:id"),
            {"id": addon_unique},
        ).scalar_one() == site_a
        assert verification.execute(
            text("SELECT site_id FROM service_addons WHERE id=:id"),
            {"id": addon_ambiguous},
        ).scalar_one_or_none() is None
    finally:
        verification.close()


def test_k26_totals_are_site_scoped_for_invalid_and_valid_sites(app_session, request):
    from core.db import get_session

    site_a = f"site-k26-a-{uuid.uuid4()}"
    site_b = f"site-k26-b-{uuid.uuid4()}"
    department_a = f"dept-k26-a-{uuid.uuid4()}"
    department_b = f"dept-k26-b-{uuid.uuid4()}"
    addon_a = f"addon-k26-a-{uuid.uuid4()}"
    addon_b = f"addon-k26-b-{uuid.uuid4()}"
    row_a = f"row-k26-a-{uuid.uuid4()}"
    row_b = f"row-k26-b-{uuid.uuid4()}"

    def cleanup_k26_rows() -> None:
        cleanup = get_session()
        try:
            cleanup.execute(
                text("DELETE FROM department_service_addons WHERE id IN (:row_a, :row_b)"),
                {"row_a": row_a, "row_b": row_b},
            )
            cleanup.execute(
                text("DELETE FROM service_addons WHERE id IN (:addon_a, :addon_b)"),
                {"addon_a": addon_a, "addon_b": addon_b},
            )
            cleanup.execute(
                text(
                    "DELETE FROM departments WHERE id IN (:department_a, :department_b)"
                ),
                {"department_a": department_a, "department_b": department_b},
            )
            cleanup.execute(
                text("DELETE FROM sites WHERE id IN (:site_a, :site_b)"),
                {"site_a": site_a, "site_b": site_b},
            )
            cleanup.commit()
        finally:
            cleanup.close()

    request.addfinalizer(cleanup_k26_rows)
    db = get_session()
    try:
        _ensure_service_addons_tables(db)
        db.execute(
            text(
                "INSERT INTO sites(id, tenant_id, name) VALUES"
                "(:site_a, 1, 'K26 A'), (:site_b, 1, 'K26 B')"
            ),
            {"site_a": site_a, "site_b": site_b},
        )
        db.execute(
            text(
                "INSERT INTO departments("
                "id, site_id, name, resident_count_mode, resident_count_fixed"
                ") VALUES"
                "(:department_a, :site_a, 'K26 Dept A', 'fixed', 10),"
                "(:department_b, :site_b, 'K26 Dept B', 'fixed', 10)"
            ),
            {
                "department_a": department_a,
                "department_b": department_b,
                "site_a": site_a,
                "site_b": site_b,
            },
        )
        db.execute(
            text(
                "INSERT INTO service_addons("
                "id, site_id, name, addon_family, is_active, created_at"
                ") VALUES"
                "(:addon_a, :site_a, 'K26 Invalid', 'ovrigt', 1, CURRENT_TIMESTAMP),"
                "(:addon_b, :site_b, 'K26 Valid', 'ovrigt', 1, CURRENT_TIMESTAMP)"
            ),
            {
                "addon_a": addon_a,
                "addon_b": addon_b,
                "site_a": site_a,
                "site_b": site_b,
            },
        )
        db.execute(
            text(
                "INSERT INTO department_service_addons("
                "id, department_id, addon_id, service_scope, quantity_mode,"
                "lunch_count, dinner_count"
                ") VALUES"
                "(:row_a, :department_a, :addon_a, 'breakfast', 'custom', 5, NULL),"
                "(:row_b, :department_b, :addon_b, 'lunch', 'custom', 4, NULL)"
            ),
            {
                "row_a": row_a,
                "row_b": row_b,
                "department_a": department_a,
                "department_b": department_b,
                "addon_a": addon_a,
                "addon_b": addon_b,
            },
        )
        db.commit()
    finally:
        db.close()

    totals_repo = DepartmentServiceAddonsRepo()
    for totals in (
        totals_repo.list_totals_for_site_meal(site_b, "lunch"),
        totals_repo.list_totals_for_site_meal_with_context(
            site_b, "lunch", year=2026, week=40, weekday=2
        ),
    ):
        assert [(row["addon_name"], row["total_count"]) for row in totals] == [
            ("K26 Valid", 4)
        ]

    for method in (
        lambda: totals_repo.list_totals_for_site_meal(site_a, "lunch"),
        lambda: totals_repo.list_totals_for_site_meal_with_context(
            site_a, "lunch", year=2026, week=40, weekday=2
        ),
    ):
        with pytest.raises(ServiceAddonDataIntegrityError) as exc_info:
            method()
        assert exc_info.value.row_id == row_a
        assert exc_info.value.site_id == site_a

    verification = get_session()
    try:
        assert verification.execute(
            text("SELECT site_id FROM service_addons WHERE id=:id"),
            {"id": addon_b},
        ).scalar_one() == site_b
        assert verification.execute(
            text("SELECT service_scope FROM department_service_addons WHERE id=:id"),
            {"id": row_a},
        ).scalar_one() == "breakfast"
    finally:
        verification.close()
