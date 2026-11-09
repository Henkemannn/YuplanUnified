from __future__ import annotations

import gc
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text

from core.app_factory import create_app
from core.db import create_all, get_session

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
_TEMP_DB_DIRS: list[str] = []


def _client():
    db_dir = tempfile.mkdtemp(prefix="builder_menu_context_api_")
    _TEMP_DB_DIRS.append(db_dir)
    db_path = os.path.join(db_dir, "test_app.db")
    builder_db_path = os.path.join(db_dir, "builder.db")
    previous_builder_db_path = os.environ.get("BUILDER_DB_PATH")
    os.environ["BUILDER_DB_PATH"] = builder_db_path
    try:
        app = create_app(
            {
                "TESTING": True,
                "database_url": f"sqlite:///{db_path}",
                "BUILDER_DB_PATH": builder_db_path,
                "SECRET_KEY": "test",
                "FORCE_DB_REINIT": True,
            }
        )
    finally:
        if previous_builder_db_path is None:
            os.environ.pop("BUILDER_DB_PATH", None)
        else:
            os.environ["BUILDER_DB_PATH"] = previous_builder_db_path
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO tenants (id, name, active) "
                    "VALUES (1, 'Tenant 1', 1)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO sites (id, name, tenant_id, version) "
                    "VALUES ('site_1', 'Site 1', 1, 0)"
                )
            )
            db.execute(
                text("INSERT INTO tenants (id, name, active) VALUES (2, 'Tenant 2', 1)")
            )
            db.execute(
                text(
                    "INSERT INTO sites (id, name, tenant_id, version) "
                    "VALUES ('site_2', 'Site 2', 1, 0)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO sites (id, name, tenant_id, version) "
                    "VALUES ('site_2_foreign', 'Foreign Site 2', 2, 0)"
                )
            )
            db.commit()
        finally:
            db.close()
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["tenant_id"] = 1
        session["role"] = "admin"
        session["site_id"] = "site_1"
    return client


def teardown_module() -> None:
    from core import db as db_mod

    if db_mod._SessionFactory is not None:
        db_mod._SessionFactory.remove()
    if db_mod._engine is not None:
        db_mod._engine.dispose()
    db_mod._SessionFactory = None
    db_mod._engine = None
    gc.collect()
    for db_dir in _TEMP_DB_DIRS:
        shutil.rmtree(db_dir)
    _TEMP_DB_DIRS.clear()


def test_create_menu_endpoint() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    assert body.get("ok") is True
    assert body.get("menu", {}).get("menu_id") == "menu_1"
    assert body.get("menu", {}).get("site_id") == "site_1"


def test_create_menu_endpoint_supports_title_and_generated_menu_id() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/menus",
        json={"title": "Week 16", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    menu = body.get("menu") or {}
    assert body.get("ok") is True
    assert isinstance(menu.get("menu_id"), str)
    assert menu.get("menu_id", "").startswith("menu_")
    assert menu.get("title") == "Week 16"


def test_menu_context_rejects_foreign_menu_and_site_access() -> None:
    client = _client()
    own_menu = client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_own", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    assert own_menu.status_code == 201

    foreign_site_create = client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_bad", "site_id": "site_2", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    assert foreign_site_create.status_code == 400

    with client.session_transaction() as session:
        session["tenant_id"] = 2
        session["site_id"] = "site_2_foreign"
    foreign_menu = client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_foreign", "site_id": "site_2_foreign", "week_key": "2026-W16"},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )
    assert foreign_menu.status_code == 201
    foreign_row = client.post(
        "/api/builder/menus/menu_foreign/rows",
        json={
            "day": "monday",
            "display_label": "Foreign empty",
            "composition_ref_type": "empty",
        },
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )
    assert foreign_row.status_code == 201
    foreign_detail_id = (foreign_row.get_json() or {}).get("menu_detail", {}).get(
        "menu_detail_id"
    )

    with client.session_transaction() as session:
        session["tenant_id"] = 1
        session["site_id"] = "site_1"
        session["site_id"] = "site_1"

    listed = client.get("/api/builder/menus", headers=HEADERS)
    assert listed.status_code == 200
    assert [item["menu_id"] for item in (listed.get_json() or {}).get("menus", [])] == [
        "menu_own"
    ]
    assert client.get("/api/builder/menus/menu_foreign/rows", headers=HEADERS).status_code == 400
    assert client.post(
        "/api/builder/menus/menu_foreign/rows",
        json={
            "day": "tuesday",
            "display_label": "Denied",
            "composition_ref_type": "empty",
        },
        headers=HEADERS,
    ).status_code == 400
    assert client.patch(
        f"/api/builder/menus/menu_foreign/rows/{foreign_detail_id}",
        json={"composition_ref_type": "empty"},
        headers=HEADERS,
    ).status_code == 400
    assert client.delete(
        f"/api/builder/menus/menu_foreign/rows/{foreign_detail_id}",
        headers=HEADERS,
    ).status_code == 400


def test_add_and_list_composition_menu_rows_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16", "title": "Week 16"},
        headers=HEADERS,
    )

    created = client.post(
        "/api/builder/menus/menu_1/rows",
        json={
            "day": "monday",
            "meal_slot": "lunch",
            "composition_id": "plate_1",
            "note": "main",
        },
        headers=HEADERS,
    )
    assert created.status_code == 201
    created_body = created.get_json() or {}
    detail = created_body.get("menu_detail") or {}
    assert detail.get("composition_ref_type") == "composition"
    assert detail.get("composition_id") == "plate_1"
    assert detail.get("unresolved_text") is None

    listed = client.get("/api/builder/menus/menu_1/rows", headers=HEADERS)
    assert listed.status_code == 200
    listed_body = listed.get_json() or {}
    rows = listed_body.get("rows") or []
    assert listed_body.get("count") == 1
    assert rows[0].get("day") == "monday"
    assert rows[0].get("meal_slot") == "lunch"
    assert rows[0].get("composition_ref_type") == "composition"
    assert rows[0].get("composition_id") == "plate_1"
    assert rows[0].get("composition_name") == "Fish Plate"
    assert rows[0].get("unresolved_text") is None


def test_add_update_and_clear_empty_menu_row_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )

    created = client.post(
        "/api/builder/menus/menu_1/rows",
        json={
            "day": "monday",
            "display_label": "Farmors favorit",
            "composition_ref_type": "empty",
            "sort_order": 5,
        },
        headers=HEADERS,
    )
    assert created.status_code == 201
    created_detail = (created.get_json() or {}).get("menu_detail") or {}
    detail_id = created_detail.get("menu_detail_id")
    assert created_detail.get("composition_ref_type") == "empty"
    assert created_detail.get("display_label") == "Farmors favorit"
    assert created_detail.get("row_kind") == "dynamic"
    assert created_detail.get("meal_slot", "").startswith("slot_")
    assert "Farmors favorit" not in created_detail.get("meal_slot", "")

    updated = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={"composition_ref_type": "composition", "day": "monday", "meal_slot": created_detail.get("meal_slot"), "composition_id": "plate_1"},
        headers=HEADERS,
    )
    assert updated.status_code == 200
    updated_detail = (updated.get_json() or {}).get("menu_detail") or {}
    assert updated_detail.get("menu_detail_id") == detail_id
    assert updated_detail.get("display_label") == "Farmors favorit"
    assert updated_detail.get("row_kind") == "dynamic"
    assert updated_detail.get("composition_ref_type") == "composition"
    assert updated_detail.get("composition_id") == "plate_1"

    cleared = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={"composition_ref_type": "empty"},
        headers=HEADERS,
    )
    assert cleared.status_code == 200
    cleared_detail = (cleared.get_json() or {}).get("menu_detail") or {}
    assert cleared_detail.get("menu_detail_id") == detail_id
    assert cleared_detail.get("display_label") == "Farmors favorit"
    assert cleared_detail.get("row_kind") == "dynamic"
    assert cleared_detail.get("composition_ref_type") == "empty"
    assert cleared_detail.get("composition_id") is None
    assert cleared_detail.get("unresolved_text") is None


def test_edit_menu_row_endpoint_switches_composition_and_updates_fields() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_2", "composition_name": "Veg Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    created = client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1", "sort_order": 5},
        headers=HEADERS,
    )
    detail_id = ((created.get_json() or {}).get("menu_detail") or {}).get("menu_detail_id")

    updated = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={
            "day": "tuesday",
            "meal_slot": "dinner",
            "composition_id": "plate_2",
            "note": "updated",
            "sort_order": 1,
        },
        headers=HEADERS,
    )

    assert updated.status_code == 200
    body = updated.get_json() or {}
    detail = body.get("menu_detail") or {}
    assert detail.get("day") == "tuesday"
    assert detail.get("meal_slot") == "dinner"
    assert detail.get("composition_ref_type") == "composition"
    assert detail.get("composition_id") == "plate_2"
    assert detail.get("unresolved_text") is None
    assert detail.get("sort_order") == 1


def test_update_menu_row_endpoint_selection_group_tristate() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_2", "composition_name": "Veg Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    created = client.post(
        "/api/builder/menus/menu_1/rows",
        json={
            "day": "monday",
            "meal_slot": "lunch",
            "composition_id": "plate_1",
            "selection_group_id": "grp_x",
        },
        headers=HEADERS,
    )
    detail_id = ((created.get_json() or {}).get("menu_detail") or {}).get("menu_detail_id")

    preserved = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1"},
        headers=HEADERS,
    )
    preserved_detail = (preserved.get_json() or {}).get("menu_detail") or {}
    assert preserved.status_code == 200
    assert preserved_detail.get("selection_group_id") == "grp_x"

    cleared = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1", "selection_group_id": None},
        headers=HEADERS,
    )
    cleared_detail = (cleared.get_json() or {}).get("menu_detail") or {}
    assert cleared.status_code == 200
    assert cleared_detail.get("selection_group_id") is None

    reassigned = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_2", "selection_group_id": "grp_y"},
        headers=HEADERS,
    )
    reassigned_detail = (reassigned.get_json() or {}).get("menu_detail") or {}
    assert reassigned.status_code == 200
    assert reassigned_detail.get("composition_id") == "plate_2"
    assert reassigned_detail.get("selection_group_id") == "grp_y"


def test_delete_menu_row_endpoint_removes_row() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    created = client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1"},
        headers=HEADERS,
    )
    detail_id = ((created.get_json() or {}).get("menu_detail") or {}).get("menu_detail_id")

    deleted = client.delete(f"/api/builder/menus/menu_1/rows/{detail_id}", headers=HEADERS)

    assert deleted.status_code == 200
    listed = client.get("/api/builder/menus/menu_1/rows", headers=HEADERS)
    rows = (listed.get_json() or {}).get("rows") or []
    assert rows == []


def test_create_empty_menu_row_endpoint_creates_dynamic_row_with_next_sort_order() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1", "sort_order": 30},
        headers=HEADERS,
    )

    created = client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "display_label": "Lunch extra", "composition_ref_type": "empty"},
        headers=HEADERS,
    )

    assert created.status_code == 201
    body = created.get_json() or {}
    detail = body.get("menu_detail") or {}
    assert detail.get("composition_ref_type") == "empty"
    assert detail.get("row_kind") == "dynamic"
    assert detail.get("display_label") == "Lunch extra"
    assert detail.get("sort_order") == 40

    listed = client.get("/api/builder/menus/menu_1/rows", headers=HEADERS)
    rows = (listed.get_json() or {}).get("rows") or []
    assert len(rows) == 2
    assert rows[1].get("is_empty") is True
    assert rows[1].get("row_kind") == "dynamic"


def test_list_menu_rows_endpoint_orders_by_sort_order() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "wednesday", "meal_slot": "dinner", "composition_id": "plate_1", "sort_order": 20},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1", "sort_order": 10},
        headers=HEADERS,
    )

    listed = client.get("/api/builder/menus/menu_1/rows", headers=HEADERS)

    assert listed.status_code == 200
    rows = (listed.get_json() or {}).get("rows") or []
    assert len(rows) == 2
    assert rows[0].get("sort_order") == 10
    assert rows[1].get("sort_order") == 20


def test_list_menu_rows_endpoint_includes_grouped_week_workspace_payload() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1", "sort_order": 10},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "dinner", "composition_id": "plate_1", "sort_order": 20},
        headers=HEADERS,
    )

    listed = client.get("/api/builder/menus/menu_1/rows", headers=HEADERS)

    assert listed.status_code == 200
    body = listed.get_json() or {}
    groups = body.get("groups") or []
    assert [
        (group.get("day"), group.get("meal_slot"))
        for group in groups
    ] == [("monday", "lunch"), ("monday", "dinner")]
    assert groups[0].get("count") == 1
    assert (groups[0].get("rows") or [])[0].get("composition_name") == "Fish Plate"


def test_list_menu_rows_grouped_marks_unresolved_rows_distinct() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )

    listed = client.get("/api/builder/menus/menu_1/rows", headers=HEADERS)

    assert listed.status_code == 200
    body = listed.get_json() or {}
    groups = body.get("groups") or []
    first_row = ((groups[0].get("rows") or [{}])[0])
    assert first_row.get("composition_ref_type") == "unresolved"
    assert first_row.get("is_unresolved") is True
    assert first_row.get("unresolved_text") == "No Match"


def test_menu_composition_adapter_endpoint_resolves_composition_components_and_roles() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_1/components",
        json={"component_name": "Fish", "role": "main"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_1/components",
        json={"component_name": "Dill Sauce", "role": "sauce"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1"},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/menus/menu_1/adapter/compositions", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    payload = body.get("payload") or {}
    assert body.get("ok") is True
    assert payload.get("adapter_version") == "menu-composition-adapter/v1.2"
    assert payload.get("menu", {}).get("menu_id") == "menu_1"
    rows = payload.get("rows") or []
    assert len(rows) == 1
    resolution = rows[0].get("resolution") or {}
    assert resolution.get("kind") == "composition"
    composition = resolution.get("composition") or {}
    assert composition.get("composition_id") == "plate_1"
    components = composition.get("components") or []
    assert [item.get("component_id") for item in components] == ["fish", "dill_sauce"]
    assert [item.get("role") for item in components] == ["main", "sauce"]
    readiness = payload.get("readiness") or {}
    assert readiness.get("total_rows") == 1
    assert readiness.get("resolved_rows") == 1
    assert readiness.get("unresolved_rows") == 0
    assert readiness.get("rows_with_roles") == 1
    assert readiness.get("rows_missing_roles") == 0


def test_menu_composition_adapter_endpoint_handles_unresolved_row_explicitly() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/menus/menu_1/adapter/compositions", headers=HEADERS)

    assert rv.status_code == 200
    payload = (rv.get_json() or {}).get("payload") or {}
    rows = payload.get("rows") or []
    assert len(rows) == 1
    resolution = rows[0].get("resolution") or {}
    assert resolution.get("kind") == "unresolved"
    assert resolution.get("composition") is None
    assert resolution.get("unresolved_text") == "No Match"


def test_menu_composition_adapter_endpoint_excludes_production_and_recipe_fields() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1"},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/menus/menu_1/adapter/compositions", headers=HEADERS)

    assert rv.status_code == 200
    payload = (rv.get_json() or {}).get("payload") or {}
    row = (payload.get("rows") or [{}])[0]
    forbidden = {
        "quantity",
        "quantity_value",
        "ingredient",
        "ingredients",
        "recipe",
        "recipe_id",
        "target_portions",
        "total_cost",
    }
    resolution = row.get("resolution") or {}
    assert forbidden.isdisjoint(set(resolution.keys()))
    composition = resolution.get("composition") or {}
    assert forbidden.isdisjoint(set(composition.keys()))


def test_menu_composition_adapter_endpoint_supports_menu_detail_filter() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    first = client.post(
        "/api/builder/menus/menu_1/rows",
        json={
            "menu_detail_id": "menu_1-row-a",
            "day": "monday",
            "meal_slot": "lunch",
            "composition_id": "plate_1",
        },
        headers=HEADERS,
    )
    assert first.status_code == 201
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "dinner", "raw_text": "No Match"}]},
        headers=HEADERS,
    )

    rv = client.get(
        "/api/builder/menus/menu_1/adapter/compositions?menu_detail_id=menu_1-row-a",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    payload = (rv.get_json() or {}).get("payload") or {}
    rows = payload.get("rows") or []
    assert len(rows) == 1
    assert rows[0].get("menu_detail", {}).get("menu_detail_id") == "menu_1-row-a"


def test_menu_composition_grouped_adapter_endpoint_groups_rows_by_day_and_meal() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_1/components",
        json={"component_name": "Fish", "role": "main"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1", "sort_order": 10},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "dinner", "raw_text": "No Match"}]},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/menus/menu_1/adapter/compositions/grouped", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    payload = body.get("payload") or {}
    assert body.get("ok") is True
    assert payload.get("adapter_version") == "menu-composition-adapter/v1.2"
    assert payload.get("menu", {}).get("menu_id") == "menu_1"
    assert payload.get("count") == 2
    days = payload.get("days") or []
    assert len(days) == 1
    assert days[0].get("day") == "monday"
    meals = days[0].get("meals") or []
    assert [meal.get("meal_slot") for meal in meals] == ["dinner", "lunch"]

    lunch_rows = next(meal.get("rows") for meal in meals if meal.get("meal_slot") == "lunch")
    resolution = (lunch_rows or [{}])[0].get("resolution") or {}
    assert resolution.get("kind") == "composition"
    components = ((resolution.get("composition") or {}).get("components") or [])
    assert [item.get("component_id") for item in components] == ["fish"]
    assert [item.get("role") for item in components] == ["main"]
    readiness = payload.get("readiness") or {}
    assert readiness.get("total_rows") == 2
    assert readiness.get("resolved_rows") == 1
    assert readiness.get("unresolved_rows") == 1
    assert readiness.get("rows_with_roles") == 1
    assert readiness.get("rows_missing_roles") == 0


def test_menu_composition_grouped_adapter_endpoint_keeps_unresolved_visible() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "dinner", "raw_text": "No Match"}]},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/menus/menu_1/adapter/compositions/grouped", headers=HEADERS)

    assert rv.status_code == 200
    payload = (rv.get_json() or {}).get("payload") or {}
    rows = (((payload.get("days") or [{}])[0].get("meals") or [{}])[0].get("rows") or [])
    assert len(rows) == 1
    resolution = rows[0].get("resolution") or {}
    assert resolution.get("kind") == "unresolved"
    assert resolution.get("composition") is None
    assert resolution.get("unresolved_text") == "No Match"


def test_menu_composition_grouped_adapter_endpoint_excludes_production_fields() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1"},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/menus/menu_1/adapter/compositions/grouped", headers=HEADERS)

    assert rv.status_code == 200
    payload = (rv.get_json() or {}).get("payload") or {}
    row = (((payload.get("days") or [{}])[0].get("meals") or [{}])[0].get("rows") or [{}])[0]
    forbidden = {
        "quantity",
        "quantity_value",
        "ingredient",
        "ingredients",
        "recipe",
        "recipe_id",
        "target_portions",
        "total_cost",
    }
    resolution = row.get("resolution") or {}
    assert forbidden.isdisjoint(set(resolution.keys()))
    composition = resolution.get("composition") or {}
    assert forbidden.isdisjoint(set(composition.keys()))


def test_menu_composition_production_shape_endpoint_returns_role_aware_structure() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_1/components",
        json={"component_name": "Fish", "role": "main"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_1/components",
        json={"component_name": "Dill Sauce", "role": "sauce"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1", "sort_order": 10},
        headers=HEADERS,
    )

    rv = client.get(
        "/api/builder/menus/menu_1/adapter/compositions/production-shape",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    payload = (rv.get_json() or {}).get("payload") or {}
    assert payload.get("adapter_version") == "menu-composition-adapter/v1.3-production-shape"
    blocks = payload.get("context_blocks") or []
    assert len(blocks) == 1
    assert blocks[0].get("context") == {"day": "monday", "meal_slot": "lunch"}
    compositions = blocks[0].get("compositions") or []
    assert len(compositions) == 1
    composition = (compositions[0] or {}).get("composition") or {}
    assert composition.get("composition_id") == "plate_1"
    role_groups = composition.get("role_groups") or []
    assert [item.get("role") for item in role_groups] == ["main", "sauce"]


def test_menu_composition_production_shape_endpoint_keeps_unresolved_rows_visible() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "dinner", "raw_text": "No Match"}]},
        headers=HEADERS,
    )

    rv = client.get(
        "/api/builder/menus/menu_1/adapter/compositions/production-shape",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    payload = (rv.get_json() or {}).get("payload") or {}
    blocks = payload.get("context_blocks") or []
    assert len(blocks) == 1
    unresolved_rows = blocks[0].get("unresolved_rows") or []
    assert len(unresolved_rows) == 1
    assert unresolved_rows[0].get("unresolved_text") == "No Match"


def test_menu_composition_production_shape_endpoint_excludes_production_fields() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1"},
        headers=HEADERS,
    )

    rv = client.get(
        "/api/builder/menus/menu_1/adapter/compositions/production-shape",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    payload = (rv.get_json() or {}).get("payload") or {}
    forbidden = {
        "quantity",
        "quantity_value",
        "ingredient",
        "ingredients",
        "recipe",
        "recipe_id",
        "target_portions",
        "total_cost",
        "prep",
    }
    block = (payload.get("context_blocks") or [{}])[0]
    assert forbidden.isdisjoint(set(block.keys()))
    composition = ((((block.get("compositions") or [{}])[0]).get("composition") or {}))
    assert forbidden.isdisjoint(set(composition.keys()))


def test_import_rows_endpoint_with_resolved_and_unresolved() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )

    rv = client.post(
        "/api/builder/menus/menu_1/import",
        json={
            "rows": [
                {"day": "monday", "meal_slot": "lunch", "raw_text": "Fish Plate"},
                {"day": "monday", "meal_slot": "dinner", "raw_text": "Unknown Dish"},
            ]
        },
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    summary = body.get("summary", {})
    assert body.get("ok") is True
    assert summary.get("imported_count") == 2
    assert summary.get("resolved_count") == 1
    assert summary.get("unresolved_count") == 1


def test_unresolved_listing_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/menus/menu_1/unresolved", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    assert body.get("count") == 1
    unresolved = body.get("unresolved") or []
    assert unresolved[0]["composition_ref_type"] == "unresolved"
    assert unresolved[0]["unresolved_text"] == "No Match"


def test_cost_overview_endpoint_with_target_portions_query_param() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "Unknown Dish"}]},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/menus/menu_1/cost-overview?target_portions=5", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    overview = body.get("overview", {})
    assert body.get("ok") is True
    assert overview.get("menu_id") == "menu_1"
    assert overview.get("unresolved_count") == 1
    detail_costs = overview.get("detail_costs") or []
    assert len(detail_costs) == 1
    assert detail_costs[0]["target_portions"] == 5
    assert detail_costs[0]["total_cost"] is None


def test_import_rows_endpoint_rejects_empty_rows() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    rv = client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": []},
        headers=HEADERS,
    )

    assert rv.status_code == 400
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


def test_resolve_menu_detail_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    imported = client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )
    detail_id = (
        (imported.get_json() or {})
        .get("summary", {})
        .get("row_results", [{}])[0]
        .get("menu_detail_id")
    )

    rv = client.post(
        "/api/builder/menus/menu_1/resolve",
        json={"menu_detail_id": detail_id, "composition_id": "plate_1"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    detail = body.get("menu_detail") or {}
    assert body.get("ok") is True
    assert detail.get("composition_ref_type") == "composition"
    assert detail.get("composition_id") == "plate_1"
    assert detail.get("unresolved_text") is None


def test_admin_builder_handoff_resolves_only_site_owned_menu_row() -> None:
    client = _client()
    created = client.post(
        "/api/builder/compositions/site",
        json={"composition_name": "Köttbullar med potatismos"},
        headers=HEADERS,
    )
    assert created.status_code == 201
    composition_id = (created.get_json() or {}).get("composition", {}).get("composition_id")

    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    imported = client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "Köttbullar med potatismos"}]},
        headers=HEADERS,
    )
    detail_id = (
        (imported.get_json() or {}).get("summary", {}).get("row_results", [{}])[0].get("menu_detail_id")
    )

    resolved = client.post(
        "/api/builder/menus/menu_1/resolve",
        json={
            "menu_detail_id": detail_id,
            "composition_id": composition_id,
            "admin_builder_handoff": True,
        },
        headers=HEADERS,
    )
    assert resolved.status_code == 200
    assert (resolved.get_json() or {}).get("menu_detail", {}).get("composition_id") == composition_id

    with client.session_transaction() as session:
        session["site_id"] = "site_2"
    foreign = client.post(
        "/api/builder/compositions/site",
        json={"composition_name": "Foreign dish"},
        headers=HEADERS,
    )
    assert foreign.status_code == 201
    foreign_id = (foreign.get_json() or {}).get("composition", {}).get("composition_id")

    with client.session_transaction() as session:
        session["site_id"] = "site_1"
    unresolved = client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "tuesday", "meal_slot": "lunch", "raw_text": "Another dish"}]},
        headers=HEADERS,
    )
    second_detail_id = (
        (unresolved.get_json() or {}).get("summary", {}).get("row_results", [{}])[0].get("menu_detail_id")
    )
    denied = client.post(
        "/api/builder/menus/menu_1/resolve",
        json={
            "menu_detail_id": second_detail_id,
            "composition_id": foreign_id,
            "admin_builder_handoff": True,
        },
        headers=HEADERS,
    )
    assert denied.status_code == 400
    assert (denied.get_json() or {}).get("error") == "bad_request"


def test_admin_builder_review_session_is_idempotent_per_source_row() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    imported = client.post(
        "/api/builder/menus/menu_1/import",
        json={
            "rows": [
                {"day": "monday", "meal_slot": "lunch", "raw_text": "Raggmunk"},
                {"day": "tuesday", "meal_slot": "lunch", "raw_text": "Linsbolognese"},
            ]
        },
        headers=HEADERS,
    )
    row_results = (imported.get_json() or {}).get("summary", {}).get("row_results", [])
    first_detail_id = row_results[0]["menu_detail_id"]
    second_detail_id = row_results[1]["menu_detail_id"]

    payload = {
        "import_type": "menu",
        "source_name": "Admin menu row review",
        "source_menu_id": "menu_1",
        "source_menu_detail_id": first_detail_id,
        "items": [{
            "item_type": "dish",
            "selected": True,
            "raw_text": "Raggmunk",
            "name": "Raggmunk",
            "components": [],
        }],
    }
    first = client.post("/api/builder/import/sessions", json=payload, headers=HEADERS)
    second = client.post("/api/builder/import/sessions", json=payload, headers=HEADERS)
    assert first.status_code == 201
    assert second.status_code == 200
    assert (second.get_json() or {}).get("reused") is True
    assert (first.get_json() or {}).get("session", {}).get("session_id") == (
        (second.get_json() or {}).get("session", {}).get("session_id")
    )

    other = dict(payload)
    other["source_menu_detail_id"] = second_detail_id
    other["items"] = [dict(payload["items"][0], raw_text="Linsbolognese", name="Linsbolognese")]
    third = client.post("/api/builder/import/sessions", json=other, headers=HEADERS)
    assert third.status_code == 201
    assert (third.get_json() or {}).get("session", {}).get("session_id") != (
        (first.get_json() or {}).get("session", {}).get("session_id")
    )


def test_update_menu_row_requires_and_uses_canonical_day_and_meal_slot() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_2", "composition_name": "Veg Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    created = client.post(
        "/api/builder/menus/menu_1/rows",
        json={
            "day": "monday",
            "meal_slot": "lunch_alt1",
            "composition_id": "plate_1",
            "menu_detail_id": "menu_1-row-1",
        },
        headers=HEADERS,
    )
    detail_id = ((created.get_json() or {}).get("menu_detail") or {}).get("menu_detail_id")

    missing_day = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={"meal_slot": "lunch_alt1", "composition_id": "plate_2"},
        headers=HEADERS,
    )
    assert missing_day.status_code == 400

    missing_meal_slot = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={"day": "monday", "composition_id": "plate_2"},
        headers=HEADERS,
    )
    assert missing_meal_slot.status_code == 400

    updated = client.patch(
        f"/api/builder/menus/menu_1/rows/{detail_id}",
        json={"day": "monday", "meal_slot": "lunch_alt1", "composition_id": "plate_2"},
        headers=HEADERS,
    )

    assert updated.status_code == 200
    body = updated.get_json() or {}
    detail = body.get("menu_detail") or {}
    assert body.get("ok") is True
    assert detail.get("day") == "monday"
    assert detail.get("meal_slot") == "lunch_alt1"
    assert detail.get("composition_id") == "plate_2"


def test_create_composition_from_row_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    imported = client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )
    detail_id = (
        (imported.get_json() or {})
        .get("summary", {})
        .get("row_results", [{}])[0]
        .get("menu_detail_id")
    )

    rv = client.post(
        "/api/builder/menus/menu_1/create-composition-from-row",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "New Plate 1",
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    assert body.get("ok") is True
    generated_id = body.get("composition", {}).get("composition_id")
    assert isinstance(generated_id, str)
    assert generated_id.startswith("cmp_")
    assert len(generated_id) == 10
    detail = body.get("menu_detail") or {}
    assert detail.get("composition_ref_type") == "composition"
    assert detail.get("composition_id") == generated_id
    assert detail.get("unresolved_text") is None


def test_create_composition_from_row_populates_suggested_components() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    imported = client.post(
        "/api/builder/menus/menu_1/import",
        json={
            "rows": [
                {
                    "day": "monday",
                    "meal_slot": "lunch",
                    "raw_text": "Kokt torsk med äggsås och pressad potatis",
                }
            ]
        },
        headers=HEADERS,
    )
    detail_id = (
        (imported.get_json() or {})
        .get("summary", {})
        .get("row_results", [{}])[0]
        .get("menu_detail_id")
    )

    rv = client.post(
        "/api/builder/menus/menu_1/create-composition-from-row",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Fiskgratang",
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    components = body.get("composition", {}).get("components") or []
    component_names = [item.get("component_name") for item in components]
    component_ids = [item.get("component_id") for item in components]
    assert component_names == ["Kokt torsk", "Äggsås", "Pressad potatis"]
    assert component_ids == ["kokt_torsk", "aggsas", "pressad_potatis"]


def test_create_composition_from_row_requires_detail_belongs_to_menu() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_2", "site_id": "site_1", "week_key": "2026-W17"},
        headers=HEADERS,
    )
    imported = client.post(
        "/api/builder/menus/menu_2/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )
    detail_id = (
        (imported.get_json() or {})
        .get("summary", {})
        .get("row_results", [{}])[0]
        .get("menu_detail_id")
    )

    rv = client.post(
        "/api/builder/menus/menu_1/create-composition-from-row",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "New Plate 2",
        },
        headers=HEADERS,
    )

    assert rv.status_code == 400


def _create_review_row(client, *, menu_id: str = "review_menu") -> str:
    client.post(
        "/api/builder/menus",
        json={"menu_id": menu_id, "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    imported = client.post(
        f"/api/builder/menus/{menu_id}/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "Bönchili med ris"}]},
        headers=HEADERS,
    )
    return str(
        (imported.get_json() or {})
        .get("summary", {})
        .get("row_results", [{}])[0]
        .get("menu_detail_id")
    )


def _create_empty_review_row(client, *, menu_id: str = "empty_review_menu") -> str:
    client.post(
        "/api/builder/menus",
        json={"menu_id": menu_id, "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    created = client.post(
        f"/api/builder/menus/{menu_id}/rows",
        json={
            "day": "monday",
            "display_label": "Manuell rätt",
            "composition_ref_type": "empty",
        },
        headers=HEADERS,
    )
    return str(
        (created.get_json() or {}).get("menu_detail", {}).get("menu_detail_id")
    )


def test_reviewed_composition_atomically_persists_components_and_row() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    existing = client.post(
        "/api/builder/components/site",
        json={"component_name": "Ris"},
        headers=HEADERS,
    )
    existing_id = (existing.get_json() or {}).get("component", {}).get("component_id")

    rv = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Bönchili med ris",
            "library_group": "lunch",
            "idempotency_key": "review-1",
            "components": [
                {"name": "Bönchili"},
                {"name": "Ris", "component_id": existing_id},
            ],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    assert body["ok"] is True
    composition = body["composition"]
    assert [item["component_name"] for item in composition["components"]] == ["Bönchili", "Ris"]
    assert composition["components"][1]["component_id"] == existing_id
    assert body["menu_detail"]["composition_id"] == composition["composition_id"]
    assert body["menu_detail"]["composition_ref_type"] == "composition"


def test_reviewed_composition_reuses_exact_and_alias_matches() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    existing = client.post(
        "/api/builder/components/site",
        json={"component_name": "Potato"},
        headers=HEADERS,
    )
    existing_id = (existing.get_json() or {}).get("component", {}).get("component_id")
    alias = client.post(
        f"/api/builder/components/{existing_id}/aliases",
        json={"alias_text": "Knöl"},
        headers=HEADERS,
    )
    assert alias.status_code == 201

    rv = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Alias dish",
            "idempotency_key": "review-alias",
            "components": [{"name": "Knöl"}],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    components = (rv.get_json() or {}).get("composition", {}).get("components") or []
    assert len(components) == 1
    assert components[0]["component_id"] == existing_id


def test_reviewed_composition_atomically_persists_empty_row_components_and_category() -> None:
    client = _client()
    detail_id = _create_empty_review_row(client)
    existing = client.post(
        "/api/builder/components/site",
        json={"component_name": "Shared soup"},
        headers=HEADERS,
    )
    existing_id = (existing.get_json() or {}).get("component", {}).get("component_id")
    category = client.post(
        "/api/builder/dish-categories",
        json={"name": "Förrätt"},
        headers=HEADERS,
    )
    category_id = ((category.get_json() or {}).get("category") or {}).get("key")

    payload = {
        "menu_detail_id": detail_id,
        "composition_name": "Svampsoppa med dillchips",
        "library_group": category_id,
        "idempotency_key": "empty-review-1",
        "components": [
            {
                "name": "Shared soup",
                "selection": "reuse",
                "component_id": existing_id,
            },
            {"name": "Dillchips variant", "selection": "new"},
        ],
    }
    first = client.post(
        "/api/builder/menus/empty_review_menu/create-reviewed-composition",
        json=payload,
        headers=HEADERS,
    )
    retry = client.post(
        "/api/builder/menus/empty_review_menu/create-reviewed-composition",
        json=payload,
        headers=HEADERS,
    )

    assert first.status_code == 201
    assert retry.status_code == 201
    first_body = first.get_json() or {}
    retry_body = retry.get_json() or {}
    composition = first_body["composition"]
    assert composition["library_group"] == category_id
    assert [item["component_id"] for item in composition["components"]][0] == existing_id
    assert composition["components"][1]["component_name"] == "Dillchips variant"
    assert retry_body["composition"]["composition_id"] == composition["composition_id"]
    assert first_body["menu_detail"]["menu_detail_id"] == detail_id
    assert first_body["menu_detail"]["composition_ref_type"] == "composition"

    library = client.get("/api/builder/components", headers=HEADERS)
    names = {
        item["component_id"]: item["component_name"]
        for item in ((library.get_json() or {}).get("components") or [])
    }
    assert names[existing_id] == "Shared soup"


def test_reviewed_composition_rejects_empty_row_on_published_menu() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={
            "menu_id": "published_empty_menu",
            "site_id": "site_1",
            "week_key": "2026-W16",
        },
        headers=HEADERS,
    )
    created = client.post(
        "/api/builder/menus/published_empty_menu/rows",
        json={
            "day": "monday",
            "display_label": "Published empty row",
            "composition_ref_type": "empty",
        },
        headers=HEADERS,
    )
    detail_id = (created.get_json() or {}).get("menu_detail", {}).get("menu_detail_id")
    from core.builder_menu_context_api import _get_menu_context_flow

    with client.application.app_context():
        _get_menu_context_flow()._menu_service.update_menu(
            "published_empty_menu",
            status="published",
        )

    response = client.post(
        "/api/builder/menus/published_empty_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Published dish",
            "idempotency_key": "published-empty-review",
            "components": [{"name": "Soup", "selection": "new"}],
        },
        headers=HEADERS,
    )

    assert response.status_code == 400
    assert "published" in str((response.get_json() or {}).get("message"))


def test_reviewed_composition_preserves_mixed_selection_modes_per_component() -> None:
    client = _client()
    existing_ids = []
    for component_name in ("Shared potato", "Shared carrot"):
        existing = client.post(
            "/api/builder/components/site",
            json={"component_name": component_name},
            headers=HEADERS,
        )
        assert existing.status_code == 201
        existing_ids.append(
            (existing.get_json() or {}).get("component", {}).get("component_id")
        )

    orders = [
        ("new", "reuse"),
        ("reuse", "new"),
        ("new", "reuse", "new"),
        ("reuse", "new", "reuse"),
    ]
    for order_index, order in enumerate(orders):
        menu_id = f"review_mixed_{order_index}"
        detail_id = _create_review_row(client, menu_id=menu_id)
        components = []
        expected_new_names = []
        reuse_index = 0
        for component_index, mode in enumerate(order):
            if mode == "reuse":
                existing_id = existing_ids[reuse_index % len(existing_ids)]
                reuse_index += 1
                components.append(
                    {
                        "name": "Shared potato"
                        if existing_id == existing_ids[0]
                        else "Shared carrot",
                        "selection": "reuse",
                        "component_id": existing_id,
                    }
                )
            else:
                variant_name = f"Mixed variant {order_index}-{component_index}"
                components.append({"name": variant_name, "selection": "new"})
                expected_new_names.append(variant_name)

        response = client.post(
            f"/api/builder/menus/{menu_id}/create-reviewed-composition",
            json={
                "menu_detail_id": detail_id,
                "composition_name": f"Mixed selection dish {order_index}",
                "idempotency_key": f"review-mixed-{order_index}",
                "components": components,
            },
            headers=HEADERS,
        )

        assert response.status_code == 201, response.get_json()
        saved = ((response.get_json() or {}).get("composition") or {}).get("components") or []
        assert len(saved) == len(order)
        expected_ids = []
        reuse_index = 0
        for mode in order:
            if mode == "reuse":
                expected_ids.append(existing_ids[reuse_index % len(existing_ids)])
                reuse_index += 1
            else:
                expected_ids.append(None)
        assert [
            item["component_id"] if mode == "reuse" else None
            for item, mode in zip(saved, order)
        ] == expected_ids
        new_components = [
            item for item in saved
            if item["component_id"] not in existing_ids
        ]
        assert [item["component_name"] for item in new_components] == expected_new_names
        assert len({item["component_id"] for item in new_components}) == len(new_components)


def test_reviewed_composition_can_create_an_explicit_new_variant() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    existing = client.post(
        "/api/builder/components/site",
        json={"component_name": "Potato"},
        headers=HEADERS,
    )
    existing_id = (existing.get_json() or {}).get("component", {}).get("component_id")

    rv = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Variant dish",
            "idempotency_key": "review-new-variant",
            "components": [{"name": "Potato variant", "selection": "new"}],
        },
        headers=HEADERS,
    )
    retry = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Variant dish",
            "idempotency_key": "review-new-variant",
            "components": [{"name": "Potato variant", "selection": "new"}],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    assert retry.status_code == 201
    component = ((rv.get_json() or {}).get("composition") or {}).get("components", [])[0]
    retry_component = ((retry.get_json() or {}).get("composition") or {}).get("components", [])[0]
    assert component["component_id"] != existing_id
    assert component["component_name"] == "Potato variant"
    assert retry_component["component_id"] == component["component_id"]

    library = client.get("/api/builder/components", headers=HEADERS)
    assert library.status_code == 200
    names_by_id = {
        item["component_id"]: item["component_name"]
        for item in ((library.get_json() or {}).get("components") or [])
    }
    assert names_by_id[existing_id] == "Potato"
    assert names_by_id[component["component_id"]] == "Potato variant"


def test_reviewed_composition_new_variant_does_not_reuse_alias() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    existing = client.post(
        "/api/builder/components/site",
        json={"component_name": "Potato"},
        headers=HEADERS,
    )
    existing_id = (existing.get_json() or {}).get("component", {}).get("component_id")
    assert client.post(
        f"/api/builder/components/{existing_id}/aliases",
        json={"alias_text": "Knöl"},
        headers=HEADERS,
    ).status_code == 201

    rv = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Alias variant dish",
            "idempotency_key": "review-new-alias-variant",
            "components": [{"name": "Knöl", "selection": "new"}],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    component = ((rv.get_json() or {}).get("composition") or {}).get("components", [])[0]
    assert component["component_id"] != existing_id
    assert component["component_name"] == "Knöl"


def test_reviewed_composition_rejects_same_site_new_variant_name() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    assert client.post(
        "/api/builder/components/site",
        json={"component_name": "Potato"},
        headers=HEADERS,
    ).status_code == 201

    rv = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Duplicate variant dish",
            "idempotency_key": "review-duplicate-variant",
            "components": [{"name": "Potato", "selection": "new"}],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 400
    assert "already exists in this site" in str((rv.get_json() or {}).get("message"))


def test_reviewed_composition_explicit_reuse_requires_accessible_component_id() -> None:
    client = _client()
    detail_id = _create_review_row(client)

    rv = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Missing reuse choice",
            "idempotency_key": "review-missing-reuse-id",
            "components": [{"name": "Potato", "selection": "reuse"}],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 400
    assert "component_id is required for reuse" in str((rv.get_json() or {}).get("message"))


def test_reviewed_composition_retry_is_idempotent_and_payload_conflict_is_explicit() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    payload = {
        "menu_detail_id": detail_id,
        "composition_name": "Bönchili med ris",
        "idempotency_key": "review-retry",
        "components": [{"name": "Bönchili"}, {"name": "Ris"}],
    }

    first = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json=payload,
        headers=HEADERS,
    )
    second = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json=payload,
        headers=HEADERS,
    )
    conflict = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={**payload, "composition_name": "Changed name"},
        headers=HEADERS,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert (
        (first.get_json() or {})["composition"]["composition_id"]
        == (second.get_json() or {})["composition"]["composition_id"]
    )
    assert conflict.status_code == 409


def test_reviewed_composition_rejects_ambiguous_component_without_choice() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    for name in ("Tomato sauce", "Tomato soup"):
        assert client.post(
            "/api/builder/components/site",
            json={"component_name": name},
            headers=HEADERS,
        ).status_code in {200, 201}

    rv = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Reviewed dish",
            "idempotency_key": "review-ambiguous",
            "components": [{"name": "Tomato sauce soup"}],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 409
    assert "explicit match" in str((rv.get_json() or {}).get("message"))


def test_reviewed_composition_denies_foreign_site_and_published_menu() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    owned = client.post(
        "/api/builder/components/site",
        json={"component_name": "Tenant private"},
        headers=HEADERS,
    )
    owned_id = (owned.get_json() or {}).get("component", {}).get("component_id")

    with client.session_transaction() as session:
        session["site_id"] = "site_2"
        session["tenant_id"] = 1
    foreign = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Denied dish",
            "idempotency_key": "review-foreign",
            "components": [{"name": "Tenant private", "component_id": owned_id}],
        },
        headers=HEADERS,
    )
    assert foreign.status_code == 400

    with client.session_transaction() as session:
        session["site_id"] = "site_1"
        session["tenant_id"] = 2
    foreign_tenant = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Denied dish",
            "idempotency_key": "review-foreign-tenant",
            "components": [{"name": "Tenant private", "component_id": owned_id}],
        },
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )
    assert foreign_tenant.status_code == 401

    with client.session_transaction() as session:
        session["tenant_id"] = 1
        session["site_id"] = "site_1"
    from core.builder_menu_context_api import _get_menu_context_flow

    with client.application.app_context():
        flow = _get_menu_context_flow()
        menu = flow._menu_service.get_menu("review_menu")
        assert menu is not None
        flow._menu_service.update_menu("review_menu", status="published")
    published = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Denied dish",
            "idempotency_key": "review-published",
            "components": [],
        },
        headers=HEADERS,
    )
    assert published.status_code == 400
    body = published.get_json() or {}
    assert body.get("error") == "bad_request"


def test_reviewed_composition_rolls_back_every_write_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    detail_id = _create_review_row(client)
    from core.builder.builder_flow import BuilderFlow
    from core.builder_menu_context_api import _get_menu_context_flow

    original_attach = BuilderFlow.attach_existing_component_to_composition
    calls = 0

    def fail_on_second_attach(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("injected attachment failure")
        return original_attach(self, *args, **kwargs)

    monkeypatch.setattr(BuilderFlow, "attach_existing_component_to_composition", fail_on_second_attach)
    rv = client.post(
        "/api/builder/menus/review_menu/create-reviewed-composition",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Rollback dish",
            "idempotency_key": "review-rollback",
            "components": [{"name": "First"}, {"name": "Second"}],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 400
    with client.application.app_context():
        flow = _get_menu_context_flow()
        assert flow._library_flow.list_library_compositions() == []
        detail = next(
            item
            for item in flow._menu_service.list_menu_details("review_menu")
            if item.menu_detail_id == detail_id
        )
        assert detail is not None
        assert detail.composition_ref_type == "unresolved"
        assert detail.composition_id is None


def test_reviewed_composition_concurrent_same_key_returns_one_composition() -> None:
    client = _client()
    detail_id = _create_review_row(client)
    app = client.application
    payload = {
        "menu_detail_id": detail_id,
        "composition_name": "Concurrent dish",
        "idempotency_key": "review-concurrent",
        "components": [{"name": "First"}, {"name": "Second"}],
    }

    def submit() -> tuple[int, str]:
        request_client = app.test_client()
        with request_client.session_transaction() as session:
            session["user_id"] = 1
            session["tenant_id"] = 1
            session["role"] = "admin"
            session["site_id"] = "site_1"
        response = request_client.post(
            "/api/builder/menus/review_menu/create-reviewed-composition",
            json=payload,
            headers=HEADERS,
        )
        body = response.get_json() or {}
        return response.status_code, str((body.get("composition") or {}).get("composition_id") or "")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: submit(), range(2)))

    assert sorted(status for status, _ in results) == [201, 201]
    assert len({composition_id for _, composition_id in results}) == 1


def test_create_composition_from_row_requires_unresolved_row() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "existing_plate", "composition_name": "Existing Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    imported = client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )
    detail_id = (
        (imported.get_json() or {})
        .get("summary", {})
        .get("row_results", [{}])[0]
        .get("menu_detail_id")
    )
    client.post(
        "/api/builder/menus/menu_1/resolve",
        json={"menu_detail_id": detail_id, "composition_id": "existing_plate"},
        headers=HEADERS,
    )

    rv = client.post(
        "/api/builder/menus/menu_1/create-composition-from-row",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "New Plate 3",
        },
        headers=HEADERS,
    )

    assert rv.status_code == 400
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


def test_create_from_row_then_add_component_returns_updated_composition() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    imported = client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )
    detail_id = (
        (imported.get_json() or {})
        .get("summary", {})
        .get("row_results", [{}])[0]
        .get("menu_detail_id")
    )

    created = client.post(
        "/api/builder/menus/menu_1/create-composition-from-row",
        json={
            "menu_detail_id": detail_id,
            "composition_name": "Fiskgratang",
        },
        headers=HEADERS,
    )
    created_id = ((created.get_json() or {}).get("composition") or {}).get("composition_id")

    rv = client.post(
        f"/api/builder/compositions/{created_id}/components",
        json={"component_name": "Fisk", "role": "component"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    components = body.get("composition", {}).get("components") or []
    assert len(components) == 2
    component_ids = [item.get("component_id") for item in components]
    assert component_ids == ["no_match", "fisk"]
    assert all(item.get("role") == "component" for item in components)


def test_menu_declaration_readiness_endpoint_returns_row_and_component_sources() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    with_component = client.post(
        "/api/builder/compositions/plate_1/components",
        json={"component_name": "Fish", "role": "main"},
        headers=HEADERS,
    )
    component_id = (
        ((with_component.get_json() or {}).get("composition") or {}).get("components") or [{}]
    )[0].get("component_id")
    recipe = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "Fish Base", "yield_portions": 8, "visibility": "private"},
        headers=HEADERS,
    )
    recipe_id = ((recipe.get_json() or {}).get("recipe") or {}).get("recipe_id")
    client.post(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/ingredients",
        json={"ingredient_name": "Cod", "amount_value": 500, "amount_unit": "g", "trait_signals": ["fish"]},
        headers=HEADERS,
    )

    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/rows",
        json={"day": "monday", "meal_slot": "lunch", "composition_id": "plate_1"},
        headers=HEADERS,
    )

    rv = client.get(
        "/api/builder/menus/menu_1/declaration-readiness?include_declaration=1",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    readiness = body.get("readiness") or {}
    assert body.get("ok") is True
    assert body.get("declaration_enabled") is True
    assert readiness.get("menu_id") == "menu_1"
    assert readiness.get("trait_signals_present") == ["fish"]
    assert (readiness.get("conflict_preview") or {}).get("conflicts_present") == ["fish_relevant"]
    rows = readiness.get("rows") or []
    assert len(rows) == 1
    assert rows[0].get("trait_signals_present") == ["fish"]
    assert (rows[0].get("conflict_preview") or {}).get("conflicts_present") == ["fish_relevant"]
    components = rows[0].get("components") or []
    assert len(components) == 1
    assert components[0].get("component_id") == component_id
    assert components[0].get("trait_signals_present") == ["fish"]
    assert (components[0].get("conflict_preview") or {}).get("conflicts_present") == ["fish_relevant"]


def test_menu_declaration_readiness_endpoint_can_be_disabled_and_keeps_read_only_contract() -> None:
    client = _client()
    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": [{"day": "monday", "meal_slot": "lunch", "raw_text": "No Match"}]},
        headers=HEADERS,
    )

    disabled = client.get(
        "/api/builder/menus/menu_1/declaration-readiness?include_declaration=0",
        headers=HEADERS,
    )
    enabled = client.get(
        "/api/builder/menus/menu_1/declaration-readiness?include_declaration=true",
        headers=HEADERS,
    )

    assert disabled.status_code == 200
    disabled_body = disabled.get_json() or {}
    assert disabled_body.get("declaration_enabled") is False
    assert disabled_body.get("readiness") is None

    assert enabled.status_code == 200
    enabled_body = enabled.get_json() or {}
    readiness = enabled_body.get("readiness") or {}
    rows = readiness.get("rows") or []
    assert enabled_body.get("declaration_enabled") is True
    assert len(rows) == 1
    assert rows[0].get("composition_ref_type") == "unresolved"
    assert rows[0].get("components") == []
