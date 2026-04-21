from __future__ import annotations

from core.app_factory import create_app

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _client():
    app = create_app({"TESTING": True})
    return app.test_client()


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
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


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
    rows = readiness.get("rows") or []
    assert len(rows) == 1
    assert rows[0].get("trait_signals_present") == ["fish"]
    components = rows[0].get("components") or []
    assert len(components) == 1
    assert components[0].get("component_id") == component_id
    assert components[0].get("trait_signals_present") == ["fish"]


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
