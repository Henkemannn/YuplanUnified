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


def test_add_component_to_composition_endpoint() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_1", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )

    rv = client.post(
        "/api/builder/compositions/plate_1/components",
        json={"component_id": "fish", "role": "main", "sort_order": 10},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    components = body.get("composition", {}).get("components") or []
    assert len(components) == 1
    assert components[0]["component_id"] == "fish"
    assert components[0]["role"] == "main"


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
