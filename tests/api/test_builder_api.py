from __future__ import annotations

import io

from openpyxl import Workbook
from core.app_factory import create_app

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _client():
    app = create_app({"TESTING": True})
    return app.test_client()


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)

    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


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


def test_create_composition_endpoint_supports_generated_id_without_menu_context() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/compositions",
        json={
            "composition_name": "Free Dish",
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    assert body.get("ok") is True
    composition = body.get("composition") or {}
    generated_id = composition.get("composition_id")
    assert isinstance(generated_id, str)
    assert generated_id.startswith("cmp_")
    assert len(generated_id) == 10
    assert composition.get("composition_name") == "Free Dish"
    components = composition.get("components") or []
    assert len(components) == 1
    assert components[0].get("component_name") == "Free Dish"


def test_free_create_composition_seeds_persisted_component_links_and_reuses_existing() -> None:
    client = _client()
    existing = client.post(
        "/api/builder/components",
        json={"component_name": "Pannbiff"},
        headers=HEADERS,
    )
    existing_id = ((existing.get_json() or {}).get("component") or {}).get("component_id")

    created = client.post(
        "/api/builder/compositions",
        json={"composition_name": "Pannbiff med potatis"},
        headers=HEADERS,
    )

    assert created.status_code == 201
    body = created.get_json() or {}
    composition = body.get("composition") or {}
    links = composition.get("components") or []
    assert len(links) == 2
    assert links[0].get("component_id") == existing_id

    library = client.get("/api/builder/library", headers=HEADERS)
    library_components = (library.get_json() or {}).get("components") or []
    assert len([item for item in library_components if item.get("component_id") == existing_id]) == 1


def test_create_standalone_component_endpoint() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/components",
        json={"component_name": "Mashed Potatoes"},
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    assert body.get("ok") is True
    component = body.get("component") or {}
    assert component.get("component_id") == "mashed_potatoes"
    assert component.get("component_name") == "Mashed Potatoes"

    compositions = client.get("/api/builder/compositions", headers=HEADERS).get_json() or {}
    assert compositions.get("count") == 0


def test_create_standalone_component_endpoint_rejects_empty_name() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/components",
        json={"component_name": "   "},
        headers=HEADERS,
    )

    assert rv.status_code == 400
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


def test_list_reusable_components_endpoint_supports_listing_and_search() -> None:
    client = _client()
    client.post("/api/builder/components", json={"component_name": "Mashed Potatoes"}, headers=HEADERS)
    client.post("/api/builder/components", json={"component_name": "Fish Sauce"}, headers=HEADERS)

    list_rv = client.get("/api/builder/components", headers=HEADERS)
    search_rv = client.get("/api/builder/components?q=fish", headers=HEADERS)

    assert list_rv.status_code == 200
    assert search_rv.status_code == 200
    list_body = list_rv.get_json() or {}
    search_body = search_rv.get_json() or {}
    assert list_body.get("ok") is True
    assert len(list_body.get("components") or []) == 2
    assert [item.get("component_name") for item in (search_body.get("components") or [])] == ["Fish Sauce"]


def test_library_endpoint_returns_separate_sorted_components_and_compositions() -> None:
    client = _client()
    client.post("/api/builder/components", json={"component_name": "zeta"}, headers=HEADERS)
    client.post("/api/builder/components", json={"component_name": "Alpha"}, headers=HEADERS)
    client.post("/api/builder/compositions", json={"composition_name": "Zulu dish"}, headers=HEADERS)
    client.post("/api/builder/compositions", json={"composition_name": "alpha dish"}, headers=HEADERS)

    rv = client.get("/api/builder/library", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    components = body.get("components") or []
    compositions = body.get("compositions") or []
    component_names = [item.get("component_name") for item in components]
    assert "Alpha" in component_names
    assert "zeta" in component_names
    assert [item.get("composition_name") for item in compositions] == ["alpha dish", "Zulu dish"]


def test_library_endpoint_no_menu_linkage_required_and_stable_composition_id_reused() -> None:
    client = _client()
    created = client.post(
        "/api/builder/compositions",
        json={"composition_name": "Fish Soup"},
        headers=HEADERS,
    )
    created_id = ((created.get_json() or {}).get("composition") or {}).get("composition_id")
    client.post(
        "/api/builder/components",
        json={"component_name": "Mashed Potatoes"},
        headers=HEADERS,
    )

    rv = client.get("/api/builder/library", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    components = body.get("components") or []
    compositions = body.get("compositions") or []
    assert any(item.get("component_name") == "Mashed Potatoes" for item in components)
    assert any(item.get("composition_id") == created_id for item in compositions)


def test_library_reads_do_not_create_new_compositions() -> None:
    client = _client()
    created = client.post(
        "/api/builder/compositions",
        json={"composition_name": "Open me"},
        headers=HEADERS,
    )
    created_id = ((created.get_json() or {}).get("composition") or {}).get("composition_id")

    before = client.get("/api/builder/compositions", headers=HEADERS)
    before_ids = {
        item.get("composition_id")
        for item in ((before.get_json() or {}).get("compositions") or [])
    }

    first_library = client.get("/api/builder/library", headers=HEADERS)
    second_library = client.get("/api/builder/library", headers=HEADERS)

    assert first_library.status_code == 200
    assert second_library.status_code == 200
    first_ids = {
        item.get("composition_id")
        for item in ((first_library.get_json() or {}).get("compositions") or [])
    }
    second_ids = {
        item.get("composition_id")
        for item in ((second_library.get_json() or {}).get("compositions") or [])
    }
    assert created_id in first_ids
    assert first_ids == second_ids == before_ids


def test_builder_library_import_accepts_lines_without_day_or_meal() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/import",
        json={"lines": ["Kottbullar med potatismos", "Fiskgratang"]},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    summary = body.get("summary") or {}
    assert body.get("ok") is True
    assert summary.get("imported_count") == 2
    assert summary.get("created_count") == 2
    assert summary.get("reused_count") == 0


def test_builder_library_import_accepts_multiline_text_and_creates_components() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/import",
        json={"text": "Kottbullar med graddsas och rodbetor"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    summary = body.get("summary") or {}
    row = (summary.get("row_results") or [{}])[0]
    created_id = row.get("composition_id")
    compositions = client.get("/api/builder/compositions", headers=HEADERS).get_json() or {}
    created = next(
        (
            item
            for item in (compositions.get("compositions") or [])
            if item.get("composition_id") == created_id
        ),
        None,
    )

    assert summary.get("created_count") == 1
    assert created is not None
    component_names = [item.get("component_name") for item in (created.get("components") or [])]
    assert component_names == ["Kottbullar", "Graddsas", "Rodbetor"]


def test_builder_library_import_persists_and_reuses_library_components() -> None:
    client = _client()

    first = client.post(
        "/api/builder/import",
        json={"lines": ["Kottbullar med potatismos"]},
        headers=HEADERS,
    )
    assert first.status_code == 200

    second = client.post(
        "/api/builder/import",
        json={"lines": ["Kottbullar med graddsas"]},
        headers=HEADERS,
    )
    assert second.status_code == 200

    library = client.get("/api/builder/library", headers=HEADERS)
    assert library.status_code == 200
    body = library.get_json() or {}
    components = body.get("components") or []
    kottbullar = [item for item in components if (item.get("component_name") or "").lower() == "kottbullar"]
    assert len(kottbullar) == 1


def test_builder_library_import_reuses_alias_without_creating_new_composition() -> None:
    client = _client()
    first = client.post(
        "/api/builder/import",
        json={"lines": ["No Match"]},
        headers=HEADERS,
    )
    first_id = (((first.get_json() or {}).get("summary") or {}).get("row_results") or [{}])[0].get(
        "composition_id"
    )

    second = client.post(
        "/api/builder/import",
        json={"lines": ["No Match"]},
        headers=HEADERS,
    )

    assert second.status_code == 200
    body = second.get_json() or {}
    summary = body.get("summary") or {}
    row = (summary.get("row_results") or [{}])[0]
    assert summary.get("created_count") == 0
    assert summary.get("reused_count") == 1
    assert row.get("composition_id") == first_id


def test_builder_library_import_rejects_empty_payload_lines() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/import",
        json={"lines": ["   ", ""]},
        headers=HEADERS,
    )

    assert rv.status_code == 400
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


def test_builder_file_import_preview_txt_endpoint() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(b"Kottbullar med potatismos\n\nFiskgratang\n"), "library.txt")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    preview = body.get("preview") or {}
    assert body.get("ok") is True
    assert preview.get("file_type") == "txt"
    assert preview.get("line_count") == 2
    assert preview.get("lines") == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.get("preview_contract_version") == 2
    assert preview.get("importable_items") == [
        {"preview_index": 0, "line": "Kottbullar med potatismos"},
        {"preview_index": 1, "line": "Fiskgratang"},
    ]
    counts = preview.get("counts") or {}
    assert counts.get("importable") == 2
    assert counts.get("ignored") == 1


def test_builder_file_import_preview_classifies_noise_vs_importable() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(b"Alt 1\nWeek 12\nFiskgratang\n"), "library.txt")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    preview = body.get("preview") or {}
    assert preview.get("importable_lines") == ["Fiskgratang"]
    ignored = preview.get("ignored_lines") or []
    ignored_texts = {item.get("normalized_text") for item in ignored}
    assert "Alt 1" in ignored_texts
    assert "Week 12" in ignored_texts
    counts = preview.get("counts") or {}
    assert counts.get("total_classified") == 3
    assert counts.get("importable") == 1
    assert counts.get("ignored") == 2


def test_builder_file_import_preview_large_payload_keeps_contract_shape() -> None:
    client = _client()
    payload_lines = [f"Dish {index}" for index in range(1, 121)]
    payload = ("\n".join(payload_lines) + "\n").encode("utf-8")

    rv = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(payload), "library.txt")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    preview = body.get("preview") or {}
    assert preview.get("line_count") == 120
    importable_items = preview.get("importable_items") or []
    assert len(importable_items) == 120
    assert importable_items[0] == {"preview_index": 0, "line": "Dish 1"}
    assert importable_items[-1] == {"preview_index": 119, "line": "Dish 120"}
    counts = preview.get("counts") or {}
    assert counts.get("importable") == 120
    assert counts.get("ignored") == 0


def test_builder_file_import_preview_csv_endpoint_detects_text_column() -> None:
    client = _client()
    payload = b"dish_name,category\nKottbullar med potatismos,main\nFiskgratang,main\n"

    rv = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(payload), "library.csv")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    preview = body.get("preview") or {}
    assert preview.get("file_type") == "csv"
    assert preview.get("lines") == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.get("csv_column") == "dish_name"
    assert preview.get("csv_column_index") == 0


def test_builder_file_import_preview_xlsx_endpoint_detects_text_column() -> None:
    client = _client()
    payload = _xlsx_bytes(
        [
            ["dish_name", "category"],
            ["Kottbullar med potatismos", "main"],
            ["Fiskgratang", "main"],
        ]
    )

    rv = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(payload), "library.xlsx")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    preview = body.get("preview") or {}
    assert preview.get("file_type") == "xlsx"
    assert preview.get("lines") == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.get("csv_column") == "dish_name"
    assert preview.get("csv_column_index") == 0


def test_builder_file_import_preview_xlsx_supports_explicit_column_name() -> None:
    client = _client()
    payload = _xlsx_bytes(
        [
            ["id", "text", "tag"],
            ["1", "Kottbullar med potatismos", "A"],
            ["2", "Fiskgratang", "B"],
        ]
    )

    rv = client.post(
        "/api/builder/import/file/preview",
        data={
            "file": (io.BytesIO(payload), "library.xlsx"),
            "csv_column": "text",
        },
        content_type="multipart/form-data",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    preview = (rv.get_json() or {}).get("preview") or {}
    assert preview.get("file_type") == "xlsx"
    assert preview.get("importable_lines") == ["Kottbullar med potatismos", "Fiskgratang"]
    assert preview.get("csv_column") == "text"
    assert preview.get("csv_column_index") == 1


def test_builder_file_import_preview_xlsx_classifies_noise_vs_importable() -> None:
    client = _client()
    payload = _xlsx_bytes(
        [
            ["text"],
            ["Week 12"],
            ["Alt 1"],
            ["Fiskgratang"],
        ]
    )

    rv = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(payload), "library.xlsx")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    preview = (rv.get_json() or {}).get("preview") or {}
    assert preview.get("importable_lines") == ["Fiskgratang"]
    ignored = preview.get("ignored_lines") or []
    ignored_texts = {item.get("normalized_text") for item in ignored}
    assert "Week 12" in ignored_texts
    assert "Alt 1" in ignored_texts


def test_builder_file_import_confirm_reuses_hardened_pipeline() -> None:
    client = _client()
    preview_payload = b"text\nKottbullar med potatismos\n"

    preview = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(preview_payload), "library.csv")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    lines = ((preview.get_json() or {}).get("preview") or {}).get("lines") or []

    first = client.post(
        "/api/builder/import/file/confirm",
        json={"lines": lines},
        headers=HEADERS,
    )
    second = client.post(
        "/api/builder/import/file/confirm",
        json={"lines": lines},
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_summary = ((first.get_json() or {}).get("summary") or {})
    second_summary = ((second.get_json() or {}).get("summary") or {})
    assert first_summary.get("created_count") == 1
    assert second_summary.get("created_count") == 0
    assert second_summary.get("reused_count") == 1
    assert first_summary.get("created_composition_count") == 1
    assert second_summary.get("reused_composition_count") == 1
    assert first_summary.get("ignored_noise_count") == 0

    row = (first_summary.get("row_results") or [{}])[0]
    assert row.get("kind") == "composition"
    assert row.get("composition_id")


def test_builder_file_import_confirm_imports_only_preview_importable_lines() -> None:
    client = _client()
    preview_payload = b"Alt 1\nFiskgratang\nAlt 2\n"

    preview = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(preview_payload), "library.txt")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    preview_body = preview.get_json() or {}
    importable_lines = ((preview_body.get("preview") or {}).get("importable_lines") or [])
    selected_lines = importable_lines[:1]

    confirmed = client.post(
        "/api/builder/import/file/confirm",
        json={"lines": selected_lines, "ignored_noise_count": 2},
        headers=HEADERS,
    )

    assert confirmed.status_code == 200
    summary = ((confirmed.get_json() or {}).get("summary") or {})
    assert summary.get("imported_count") == 1
    assert summary.get("ignored_noise_count") == 2
    rows = summary.get("row_results") or []
    assert len(rows) == 1
    assert rows[0].get("raw_text") == "Fiskgratang"


def test_builder_file_import_confirm_reuses_pipeline_for_xlsx_preview_lines() -> None:
    client = _client()
    preview_payload = _xlsx_bytes(
        [
            ["text"],
            ["Kottbullar med potatismos"],
        ]
    )

    preview = client.post(
        "/api/builder/import/file/preview",
        data={"file": (io.BytesIO(preview_payload), "library.xlsx")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    lines = ((preview.get_json() or {}).get("preview") or {}).get("lines") or []

    first = client.post(
        "/api/builder/import/file/confirm",
        json={"lines": lines},
        headers=HEADERS,
    )
    second = client.post(
        "/api/builder/import/file/confirm",
        json={"lines": lines},
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_summary = ((first.get_json() or {}).get("summary") or {})
    second_summary = ((second.get_json() or {}).get("summary") or {})
    assert first_summary.get("created_count") == 1
    assert second_summary.get("created_count") == 0
    assert second_summary.get("reused_count") == 1

    row = (first_summary.get("row_results") or [{}])[0]
    assert row.get("kind") == "composition"
    assert row.get("composition_id")
    assert "day" not in row
    assert "meal_slot" not in row


def test_builder_file_import_confirm_summary_reports_component_creation_and_reuse() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/import/file/confirm",
        json={
            "lines": [
                "Kottbullar med potatismos",
                "Kottbullar med graddsas",
            ],
            "ignored_noise_count": 3,
        },
        headers=HEADERS,
    )

    assert rv.status_code == 200
    summary = ((rv.get_json() or {}).get("summary") or {})
    assert summary.get("imported_count") == 2
    assert summary.get("created_composition_count") == 2
    assert summary.get("reused_composition_count") == 0
    assert summary.get("created_component_count") == 3
    assert summary.get("reused_component_count") == 1
    assert summary.get("ignored_noise_count") == 3


def test_builder_file_import_confirm_response_remains_library_only() -> None:
    client = _client()

    rv = client.post(
        "/api/builder/import/file/confirm",
        json={"lines": ["Fiskgratang"]},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    summary = ((rv.get_json() or {}).get("summary") or {})
    assert "day" not in summary
    assert "meal_slot" not in summary
    assert "menu_detail_id" not in summary
    rows = summary.get("row_results") or []
    assert len(rows) == 1
    row = rows[0]
    assert "day" not in row
    assert "meal_slot" not in row
    assert "menu_detail_id" not in row


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


def test_add_component_to_composition_endpoint_allows_empty_role() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_no_role", "composition_name": "Role Free Plate"},
        headers=HEADERS,
    )

    rv = client.post(
        "/api/builder/compositions/plate_no_role/components",
        json={"component_name": "Fisk"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    components = ((rv.get_json() or {}).get("composition") or {}).get("components") or []
    assert len(components) == 1
    assert components[0].get("role") is None


def test_attach_existing_component_endpoint_reuses_component_id_and_does_not_create_duplicate_entity() -> None:
    client = _client()
    created_component = client.post(
        "/api/builder/components",
        json={"component_name": "Mashed Potatoes"},
        headers=HEADERS,
    )
    component_id = ((created_component.get_json() or {}).get("component") or {}).get("component_id")
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_attach", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )

    rv = client.post(
        "/api/builder/compositions/plate_attach/components/attach",
        json={"component_id": component_id, "role": "component"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    components = body.get("composition", {}).get("components") or []
    assert len(components) == 1
    assert components[0].get("component_id") == component_id

    listed = client.get("/api/builder/components", headers=HEADERS).get_json() or {}
    assert len([item for item in (listed.get("components") or []) if item.get("component_id") == component_id]) == 1


def test_attach_existing_component_endpoint_rejects_empty_or_invalid_id() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_invalid", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )

    empty_rv = client.post(
        "/api/builder/compositions/plate_invalid/components/attach",
        json={"component_id": "   "},
        headers=HEADERS,
    )
    invalid_rv = client.post(
        "/api/builder/compositions/plate_invalid/components/attach",
        json={"component_id": "unknown"},
        headers=HEADERS,
    )

    assert empty_rv.status_code == 400
    assert invalid_rv.status_code == 400


def test_attach_existing_component_endpoint_no_menu_linkage_required() -> None:
    client = _client()
    component = client.post(
        "/api/builder/components",
        json={"component_name": "Gravy"},
        headers=HEADERS,
    )
    component_id = ((component.get_json() or {}).get("component") or {}).get("component_id")
    composition = client.post(
        "/api/builder/compositions",
        json={"composition_name": "Fish Soup"},
        headers=HEADERS,
    )
    composition_id = ((composition.get_json() or {}).get("composition") or {}).get("composition_id")

    rv = client.post(
        "/api/builder/compositions/" + str(composition_id) + "/components/attach",
        json={"component_id": component_id, "role": "component"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("composition", {}).get("composition_id") == composition_id


def test_attach_existing_component_endpoint_prevents_duplicate_attach() -> None:
    client = _client()
    component = client.post(
        "/api/builder/components",
        json={"component_name": "Rice"},
        headers=HEADERS,
    )
    component_id = ((component.get_json() or {}).get("component") or {}).get("component_id")
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_dupe", "composition_name": "Rice Plate"},
        headers=HEADERS,
    )
    first = client.post(
        "/api/builder/compositions/plate_dupe/components/attach",
        json={"component_id": component_id, "role": "component"},
        headers=HEADERS,
    )
    second = client.post(
        "/api/builder/compositions/plate_dupe/components/attach",
        json={"component_id": component_id, "role": "component"},
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 400


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


def test_update_component_role_in_composition_endpoint_role_only() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_role_patch", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_role_patch/components",
        json={"component_name": "Fisk", "role": "component"},
        headers=HEADERS,
    )

    rv = client.patch(
        "/api/builder/compositions/plate_role_patch/components/fisk",
        json={"role": "main"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    components = ((rv.get_json() or {}).get("composition") or {}).get("components") or []
    assert len(components) == 1
    assert components[0].get("component_id") == "fisk"
    assert components[0].get("role") == "main"


def test_update_component_role_in_composition_endpoint_allows_clearing_role() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_role_clear", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_role_clear/components",
        json={"component_name": "Fisk", "role": "main"},
        headers=HEADERS,
    )

    rv = client.patch(
        "/api/builder/compositions/plate_role_clear/components/fisk",
        json={"role": "   "},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    components = ((rv.get_json() or {}).get("composition") or {}).get("components") or []
    assert len(components) == 1
    assert components[0].get("role") is None


def test_rename_component_in_composition_endpoint_can_update_name_and_role_together() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_name_role_patch", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_name_role_patch/components",
        json={"component_name": "Fisk", "role": "component"},
        headers=HEADERS,
    )

    rv = client.patch(
        "/api/builder/compositions/plate_name_role_patch/components/fisk",
        json={"component_name": "Lax", "role": "main"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    components = ((rv.get_json() or {}).get("composition") or {}).get("components") or []
    assert len(components) == 1
    assert components[0].get("component_id") == "lax"
    assert components[0].get("component_name") == "Lax"
    assert components[0].get("role") == "main"


def test_update_component_endpoint_requires_component_name_or_role() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_patch_required", "composition_name": "Fish Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_patch_required/components",
        json={"component_name": "Fisk", "role": "component"},
        headers=HEADERS,
    )

    rv = client.patch(
        "/api/builder/compositions/plate_patch_required/components/fisk",
        json={},
        headers=HEADERS,
    )

    assert rv.status_code == 400
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


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
