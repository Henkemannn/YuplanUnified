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


def test_reorder_components_endpoint_persists_order_and_sort_order() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_reorder", "composition_name": "Reorder Plate"},
        headers=HEADERS,
    )
    a = client.post(
        "/api/builder/compositions/plate_reorder/components",
        json={"component_name": "Potato", "role": "side"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_reorder/components",
        json={"component_name": "Fish", "role": "main"},
        headers=HEADERS,
    )

    components = ((a.get_json() or {}).get("composition") or {}).get("components") or []
    assert len(components) == 1
    listed_before = client.get("/api/builder/compositions", headers=HEADERS).get_json() or {}
    plate_before = next(
        item
        for item in (listed_before.get("compositions") or [])
        if item.get("composition_id") == "plate_reorder"
    )
    entries = plate_before.get("components") or []

    rv = client.patch(
        "/api/builder/compositions/plate_reorder/components/reorder",
        json={
            "ordered_entries": [
                {"component_id": entries[1].get("component_id"), "sort_order": entries[1].get("sort_order")},
                {"component_id": entries[0].get("component_id"), "sort_order": entries[0].get("sort_order")},
            ]
        },
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    after = ((body.get("composition") or {}).get("components") or [])
    assert [item.get("component_name") for item in after] == ["Fish", "Potato"]
    assert [item.get("sort_order") for item in after] == [10, 20]
    assert "primary_recipe_id" not in (after[0] if after else {})

    listed_after = client.get("/api/builder/compositions", headers=HEADERS).get_json() or {}
    plate_after = next(
        item
        for item in (listed_after.get("compositions") or [])
        if item.get("composition_id") == "plate_reorder"
    )
    reloaded = plate_after.get("components") or []
    assert [item.get("component_name") for item in reloaded] == ["Fish", "Potato"]
    assert [item.get("sort_order") for item in reloaded] == [10, 20]


def test_render_composition_text_endpoint_uses_persisted_order() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_text", "composition_name": "Text Plate"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_text/components",
        json={"component_name": "Potato", "role": "side"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_text/components",
        json={"component_name": "Fish", "role": "main"},
        headers=HEADERS,
    )

    listed = client.get("/api/builder/compositions", headers=HEADERS).get_json() or {}
    plate = next(
        item
        for item in (listed.get("compositions") or [])
        if item.get("composition_id") == "plate_text"
    )
    entries = plate.get("components") or []
    reorder = client.patch(
        "/api/builder/compositions/plate_text/components/reorder",
        json={
            "ordered_entries": [
                {"component_id": entries[1].get("component_id"), "sort_order": entries[1].get("sort_order")},
                {"component_id": entries[0].get("component_id"), "sort_order": entries[0].get("sort_order")},
            ]
        },
        headers=HEADERS,
    )
    assert reorder.status_code == 200

    rv = client.get("/api/builder/compositions/plate_text/render/text", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    rendered = body.get("rendered") or {}
    assert body.get("ok") is True
    assert rendered.get("text") == "Text Plate: Fish (main), Potato (side)"
    names = [item.get("component_name") for item in (rendered.get("components") or [])]
    assert names == ["Fish", "Potato"]
    assert [item.get("sort_order") for item in (rendered.get("components") or [])] == [10, 20]


def test_render_composition_text_endpoint_is_deterministic_and_isolated() -> None:
    client = _client()
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_a", "composition_name": "Plate A"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions",
        json={"composition_id": "plate_b", "composition_name": "Plate B"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_a/components",
        json={"component_name": "Fish"},
        headers=HEADERS,
    )
    client.post(
        "/api/builder/compositions/plate_b/components",
        json={"component_name": "Soup"},
        headers=HEADERS,
    )

    first = client.get("/api/builder/compositions/plate_a/render/text", headers=HEADERS)
    second = client.get("/api/builder/compositions/plate_a/render/text", headers=HEADERS)

    assert first.status_code == 200
    assert second.status_code == 200
    first_rendered = (first.get_json() or {}).get("rendered") or {}
    second_rendered = (second.get_json() or {}).get("rendered") or {}
    assert first_rendered.get("text") == "Plate A: Fish"
    assert second_rendered.get("text") == "Plate A: Fish"
    assert first_rendered.get("text") == second_rendered.get("text")
    assert [item.get("component_name") for item in (first_rendered.get("components") or [])] == ["Fish"]


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


def test_create_component_recipe_endpoint_requires_yield_portions_and_structured_lines() -> None:
    client = _client()
    component_rv = client.post(
        "/api/builder/components",
        json={"component_name": "Meatballs"},
        headers=HEADERS,
    )
    component_id = ((component_rv.get_json() or {}).get("component") or {}).get("component_id")

    rv = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={
            "recipe_name": "Base",
            "visibility": "site",
            "yield_portions": 24,
            "is_primary": True,
            "ingredient_lines": [
                {
                    "ingredient_name": "Potato",
                    "amount_value": 900,
                    "amount_unit": "g",
                    "note": "peeled",
                    "sort_order": 10,
                }
            ],
        },
        headers=HEADERS,
    )

    assert rv.status_code == 201
    body = rv.get_json() or {}
    recipe = body.get("recipe") or {}
    assert recipe.get("yield_portions") == 24
    lines = body.get("ingredient_lines") or []
    assert len(lines) == 1
    assert lines[0].get("ingredient_name") == "Potato"
    assert lines[0].get("amount_value") == 900.0
    assert lines[0].get("amount_unit") == "g"
    assert lines[0].get("note") == "peeled"

    list_components = client.get("/api/builder/components", headers=HEADERS)
    components = (list_components.get_json() or {}).get("components") or []
    linked = next(item for item in components if item.get("component_id") == component_id)
    assert linked.get("primary_recipe_id") == recipe.get("recipe_id")


def test_create_component_recipe_endpoint_rejects_missing_yield_portions() -> None:
    client = _client()
    component_rv = client.post(
        "/api/builder/components",
        json={"component_name": "Fish"},
        headers=HEADERS,
    )
    component_id = ((component_rv.get_json() or {}).get("component") or {}).get("component_id")

    rv = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "Base", "visibility": "private"},
        headers=HEADERS,
    )

    assert rv.status_code == 400
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


def test_add_recipe_ingredient_endpoint_accepts_structured_amount_and_reads_back() -> None:
    client = _client()
    component_rv = client.post(
        "/api/builder/components",
        json={"component_name": "Sauce"},
        headers=HEADERS,
    )
    component_id = ((component_rv.get_json() or {}).get("component") or {}).get("component_id")

    recipe_rv = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "Sauce Base", "yield_portions": 10, "visibility": "private"},
        headers=HEADERS,
    )
    recipe_id = ((recipe_rv.get_json() or {}).get("recipe") or {}).get("recipe_id")

    add_rv = client.post(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/ingredients",
        json={
            "ingredient_name": "Cream",
            "amount_value": 2.5,
            "amount_unit": "dl",
            "note": "warm",
        },
        headers=HEADERS,
    )
    get_rv = client.get(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}",
        headers=HEADERS,
    )

    assert add_rv.status_code == 201
    assert get_rv.status_code == 200
    lines = (get_rv.get_json() or {}).get("ingredient_lines") or []
    assert len(lines) == 1
    assert lines[0].get("ingredient_name") == "Cream"
    assert lines[0].get("amount_value") == 2.5
    assert lines[0].get("amount_unit") == "dl"
    assert lines[0].get("note") == "warm"


def test_set_component_primary_recipe_endpoint_rejects_recipe_from_other_component() -> None:
    client = _client()
    c1 = client.post("/api/builder/components", json={"component_name": "Fish"}, headers=HEADERS)
    c2 = client.post("/api/builder/components", json={"component_name": "Potato"}, headers=HEADERS)
    c1_id = ((c1.get_json() or {}).get("component") or {}).get("component_id")
    c2_id = ((c2.get_json() or {}).get("component") or {}).get("component_id")

    recipe_rv = client.post(
        f"/api/builder/components/{c1_id}/recipes",
        json={"recipe_name": "Fish Base", "yield_portions": 10, "visibility": "private"},
        headers=HEADERS,
    )
    recipe_id = ((recipe_rv.get_json() or {}).get("recipe") or {}).get("recipe_id")

    rv = client.patch(
        f"/api/builder/components/{c2_id}/recipes/primary",
        json={"recipe_id": recipe_id},
        headers=HEADERS,
    )

    assert rv.status_code == 400
    body = rv.get_json() or {}
    assert body.get("error") == "bad_request"


def test_list_component_recipes_endpoint_returns_component_scoped_deterministic_list() -> None:
    client = _client()
    c1 = client.post("/api/builder/components", json={"component_name": "Fish"}, headers=HEADERS)
    c2 = client.post("/api/builder/components", json={"component_name": "Potato"}, headers=HEADERS)
    c1_id = ((c1.get_json() or {}).get("component") or {}).get("component_id")
    c2_id = ((c2.get_json() or {}).get("component") or {}).get("component_id")

    r_b = client.post(
        f"/api/builder/components/{c1_id}/recipes",
        json={"recipe_name": "B Recipe", "yield_portions": 10, "visibility": "private"},
        headers=HEADERS,
    )
    r_a = client.post(
        f"/api/builder/components/{c1_id}/recipes",
        json={"recipe_name": "A Recipe", "yield_portions": 12, "visibility": "private"},
        headers=HEADERS,
    )
    client.post(
        f"/api/builder/components/{c2_id}/recipes",
        json={"recipe_name": "Other Component Recipe", "yield_portions": 8, "visibility": "private"},
        headers=HEADERS,
    )

    primary_id = ((r_b.get_json() or {}).get("recipe") or {}).get("recipe_id")
    client.patch(
        f"/api/builder/components/{c1_id}/recipes/primary",
        json={"recipe_id": primary_id},
        headers=HEADERS,
    )

    rv = client.get(f"/api/builder/components/{c1_id}/recipes", headers=HEADERS)

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    recipes = body.get("recipes") or []
    assert len(recipes) == 2
    assert recipes[0].get("recipe_id") == primary_id
    assert recipes[0].get("is_primary") is True
    assert recipes[1].get("recipe_name") == "A Recipe"
    assert body.get("component", {}).get("component_id") == c1_id

    all_ids = {item.get("recipe_id") for item in recipes}
    assert ((r_a.get_json() or {}).get("recipe") or {}).get("recipe_id") in all_ids
    assert not any(item.get("recipe_name") == "Other Component Recipe" for item in recipes)


def test_update_recipe_metadata_endpoint() -> None:
    client = _client()
    c = client.post("/api/builder/components", json={"component_name": "Fish"}, headers=HEADERS)
    component_id = ((c.get_json() or {}).get("component") or {}).get("component_id")
    created = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "Old", "yield_portions": 10, "visibility": "private", "notes": "old"},
        headers=HEADERS,
    )
    recipe_id = ((created.get_json() or {}).get("recipe") or {}).get("recipe_id")

    rv = client.patch(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}",
        json={"recipe_name": "New", "yield_portions": 24, "visibility": "site", "notes": "new"},
        headers=HEADERS,
    )

    assert rv.status_code == 200
    recipe = (rv.get_json() or {}).get("recipe") or {}
    assert recipe.get("recipe_name") == "New"
    assert recipe.get("yield_portions") == 24
    assert recipe.get("visibility") == "site"
    assert recipe.get("notes") == "new"


def test_update_and_delete_recipe_ingredient_endpoint() -> None:
    client = _client()
    c = client.post("/api/builder/components", json={"component_name": "Soup"}, headers=HEADERS)
    component_id = ((c.get_json() or {}).get("component") or {}).get("component_id")
    created = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "Base", "yield_portions": 10, "visibility": "private"},
        headers=HEADERS,
    )
    recipe_id = ((created.get_json() or {}).get("recipe") or {}).get("recipe_id")
    added = client.post(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/ingredients",
        json={"ingredient_name": "Salt", "amount_value": 10, "amount_unit": "g", "note": "initial"},
        headers=HEADERS,
    )
    line_id = ((added.get_json() or {}).get("ingredient_line") or {}).get("recipe_ingredient_line_id")

    update_rv = client.patch(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/ingredients/{line_id}",
        json={
            "ingredient_name": "Sea salt",
            "amount_value": 12,
            "amount_unit": "g",
            "note": "updated",
            "sort_order": 20,
        },
        headers=HEADERS,
    )
    delete_rv = client.delete(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/ingredients/{line_id}",
        headers=HEADERS,
    )
    detail_rv = client.get(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}",
        headers=HEADERS,
    )

    assert update_rv.status_code == 200
    line = (update_rv.get_json() or {}).get("ingredient_line") or {}
    assert line.get("ingredient_name") == "Sea salt"
    assert line.get("amount_value") == 12.0
    assert line.get("sort_order") == 20
    assert delete_rv.status_code == 200
    lines = (detail_rv.get_json() or {}).get("ingredient_lines") or []
    assert lines == []


def test_delete_recipe_endpoint_guard_for_primary_recipe() -> None:
    client = _client()
    c = client.post("/api/builder/components", json={"component_name": "Stew"}, headers=HEADERS)
    component_id = ((c.get_json() or {}).get("component") or {}).get("component_id")
    created = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "Base", "yield_portions": 8, "visibility": "private", "is_primary": True},
        headers=HEADERS,
    )
    recipe_id = ((created.get_json() or {}).get("recipe") or {}).get("recipe_id")

    blocked = client.delete(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}",
        headers=HEADERS,
    )
    clear_primary = client.patch(
        f"/api/builder/components/{component_id}/recipes/primary",
        json={"recipe_id": ""},
        headers=HEADERS,
    )
    deleted = client.delete(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}",
        headers=HEADERS,
    )

    assert blocked.status_code == 400
    assert (blocked.get_json() or {}).get("error") == "bad_request"
    assert clear_primary.status_code == 200
    assert deleted.status_code == 200


def test_update_recipe_ingredient_enforces_component_ownership() -> None:
    client = _client()
    c1 = client.post("/api/builder/components", json={"component_name": "Fish"}, headers=HEADERS)
    c2 = client.post("/api/builder/components", json={"component_name": "Potato"}, headers=HEADERS)
    c1_id = ((c1.get_json() or {}).get("component") or {}).get("component_id")
    c2_id = ((c2.get_json() or {}).get("component") or {}).get("component_id")

    created = client.post(
        f"/api/builder/components/{c1_id}/recipes",
        json={"recipe_name": "Fish Base", "yield_portions": 10, "visibility": "private"},
        headers=HEADERS,
    )
    recipe_id = ((created.get_json() or {}).get("recipe") or {}).get("recipe_id")
    added = client.post(
        f"/api/builder/components/{c1_id}/recipes/{recipe_id}/ingredients",
        json={"ingredient_name": "Salt", "amount_value": 10, "amount_unit": "g"},
        headers=HEADERS,
    )
    line_id = ((added.get_json() or {}).get("ingredient_line") or {}).get("recipe_ingredient_line_id")

    rv = client.patch(
        f"/api/builder/components/{c2_id}/recipes/{recipe_id}/ingredients/{line_id}",
        json={"ingredient_name": "Salt", "amount_value": 11, "amount_unit": "g"},
        headers=HEADERS,
    )

    assert rv.status_code == 400
    assert (rv.get_json() or {}).get("error") == "bad_request"


def test_recipe_scaling_preview_endpoint_returns_scaled_rows_and_metadata() -> None:
    client = _client()
    c = client.post("/api/builder/components", json={"component_name": "Soup"}, headers=HEADERS)
    component_id = ((c.get_json() or {}).get("component") or {}).get("component_id")

    created = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "Base", "yield_portions": 4, "visibility": "private", "notes": "v1"},
        headers=HEADERS,
    )
    recipe_id = ((created.get_json() or {}).get("recipe") or {}).get("recipe_id")

    client.post(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/ingredients",
        json={
            "ingredient_name": "Water",
            "amount_value": 2,
            "amount_unit": "l",
            "note": "cold",
            "sort_order": 10,
        },
        headers=HEADERS,
    )
    client.post(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/ingredients",
        json={"ingredient_name": "Salt", "amount_value": 8, "amount_unit": "g", "sort_order": 20},
        headers=HEADERS,
    )

    rv = client.get(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/scaling-preview?target_portions=10",
        headers=HEADERS,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    preview = body.get("preview") or {}
    assert body.get("ok") is True
    recipe = preview.get("recipe") or {}
    assert recipe.get("recipe_id") == recipe_id
    assert recipe.get("component_id") == component_id
    assert recipe.get("recipe_name") == "Base"
    assert recipe.get("notes") == "v1"
    assert preview.get("source_yield_portions") == 4
    assert preview.get("target_portions") == 10
    assert preview.get("scaling_factor") == "2.5"
    lines = preview.get("ingredient_lines") or []
    assert [item.get("ingredient_name") for item in lines] == ["Water", "Salt"]
    assert [item.get("amount_unit") for item in lines] == ["l", "g"]
    assert [item.get("original_amount_value") for item in lines] == ["2", "8"]
    assert [item.get("scaled_amount_value") for item in lines] == ["5.0", "20.0"]
    assert [item.get("note") for item in lines] == ["cold", None]


def test_recipe_scaling_preview_endpoint_rejects_invalid_target_portions() -> None:
    client = _client()
    c = client.post("/api/builder/components", json={"component_name": "Soup"}, headers=HEADERS)
    component_id = ((c.get_json() or {}).get("component") or {}).get("component_id")
    created = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "Base", "yield_portions": 4, "visibility": "private"},
        headers=HEADERS,
    )
    recipe_id = ((created.get_json() or {}).get("recipe") or {}).get("recipe_id")

    missing = client.get(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/scaling-preview",
        headers=HEADERS,
    )
    invalid = client.get(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}/scaling-preview?target_portions=0",
        headers=HEADERS,
    )

    assert missing.status_code == 400
    assert (missing.get_json() or {}).get("error") == "bad_request"
    assert invalid.status_code == 400
    assert (invalid.get_json() or {}).get("error") == "bad_request"


def test_recipe_scaling_preview_endpoint_enforces_component_ownership() -> None:
    client = _client()
    c1 = client.post("/api/builder/components", json={"component_name": "Fish"}, headers=HEADERS)
    c2 = client.post("/api/builder/components", json={"component_name": "Potato"}, headers=HEADERS)
    c1_id = ((c1.get_json() or {}).get("component") or {}).get("component_id")
    c2_id = ((c2.get_json() or {}).get("component") or {}).get("component_id")
    created = client.post(
        f"/api/builder/components/{c1_id}/recipes",
        json={"recipe_name": "Fish Base", "yield_portions": 6, "visibility": "private"},
        headers=HEADERS,
    )
    recipe_id = ((created.get_json() or {}).get("recipe") or {}).get("recipe_id")

    rv = client.get(
        f"/api/builder/components/{c2_id}/recipes/{recipe_id}/scaling-preview?target_portions=12",
        headers=HEADERS,
    )

    assert rv.status_code == 400
    assert (rv.get_json() or {}).get("error") == "bad_request"
