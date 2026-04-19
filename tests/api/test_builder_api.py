from __future__ import annotations

from core.app_factory import create_app

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_create_composition_endpoint() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/compositions",
        json={
            "composition_id": "plate_1",
            "composition_name": "Fish Plate",
            "library_group": "weekly",
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    assert body.get("ok") is True
    assert body.get("composition", {}).get("composition_id") == "plate_1"
    assert body.get("composition", {}).get("composition_name") == "Fish Plate"


def test_list_compositions_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/compositions", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    assert body.get("count") == 1
    compositions = body.get("compositions") or []
    assert compositions[0]["composition_id"] == "plate_1"


def test_add_component_to_composition_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )

    rv = client.post(
        "/api/builder/compositions/plate_1/components",
        json={"component_name": "Fisk", "role": "component"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    components = body.get("composition", {}).get("components") or []
    assert len(components) == 1
    assert components[0]["component_name"] == "Fisk"
    assert components[0]["component_id"] == "fisk"
    assert components[0]["role"] == "component"


def test_add_component_to_composition_endpoint_supports_connector_role() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_2", "composition_name": "Fish Plate 2"},
        headers=HEADERS,
    )

    rv = client.post(
        "/api/builder/compositions/plate_2/components",
        json={"component_name": "med", "role": "connector"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    components = body.get("composition", {}).get("components") or []
    assert len(components) == 1
    assert components[0]["component_id"] == "med"
    assert components[0]["role"] == "connector"


def test_remove_component_from_composition_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_3", "composition_name": "Fish Plate 3"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_3/components",
        json={"component_name": "Fisk", "role": "component"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_3/components",
        json={"component_name": "Potatis", "role": "component"},
        headers=HEADERS,
    )

    rv = client.delete(
        "/api/builder/compositions/plate_3/components/fisk",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    components = body.get("composition", {}).get("components") or []
    assert len(components) == 1
    assert components[0]["component_id"] == "potatis"


def test_rename_component_in_composition_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_4", "composition_name": "Fish Plate 4"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_4/components",
        json={"component_name": "Fisk", "role": "connector"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_4/components",
        json={"component_name": "Potatis", "role": "component"},
        headers=HEADERS,
    )

    rv = client.patch(
        "/api/builder/compositions/plate_4/components/fisk",
        json={"component_name": "Lax"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    components = body.get("composition", {}).get("components") or []
    assert [item["component_id"] for item in components] == ["lax", "potatis"]
    assert [item["component_name"] for item in components] == ["Lax", "Potatis"]
    assert components[0]["role"] == "connector"


def test_rename_component_in_composition_endpoint_preserves_swedish_component_name() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_6", "composition_name": "Fish Plate 6"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_6/components",
        json={"component_name": "Fisk", "role": "component"},
        headers=HEADERS,
    )

    rv = client.patch(
        "/api/builder/compositions/plate_6/components/fisk",
        json={"component_name": "Köttbullar"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    components = body.get("composition", {}).get("components") or []
    assert len(components) == 1
    assert components[0]["component_name"] == "Köttbullar"
    assert components[0]["component_id"] == "kottbullar"


def test_rename_component_in_composition_endpoint_rejects_empty_name() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_5", "composition_name": "Fish Plate 5"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_5/components",
        json={"component_name": "Fisk", "role": "component"},
        headers=HEADERS,
    )

    rv = client.patch(
        "/api/builder/compositions/plate_5/components/fisk",
        json={"component_name": "   "},
        headers=HEADERS,
    )

    assert rv.status_code == 400
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


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


def test_invalid_payload_handling_returns_400() -> None:
    client = _client()

    rv1 = client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1"},
        headers=HEADERS,
    )
    assert rv1.status_code == 400
    body1 = rv1.get_json() or {}
    assert body1.get("error") == "bad_request"

    client.post(
        "/api/builder/menus",
        json={"menu_id": "menu_1", "site_id": "site_1", "week_key": "2026-W16"},
        headers=HEADERS,
    )
    rv2 = client.post(
        "/api/builder/menus/menu_1/import",
        json={"rows": []},
        headers=HEADERS,
    )
    assert rv2.status_code == 400
    body2 = rv2.get_json() or {}
    assert body2.get("error") == "bad_request"


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
