from __future__ import annotations


def test_builder_import_preview_lines_classifies_importable_and_ignored(client_admin) -> None:
    rv = client_admin.post(
        "/api/builder/import/preview-lines",
        json={"lines": ["Week 12", "Monday", "Kottbullar med potatismos", "Alt 1", "Fiskgratang"]},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    data = rv.get_json() or {}
    assert data.get("ok") is True

    preview = data.get("preview") or {}
    importable = preview.get("importable_lines") or []
    ignored = preview.get("ignored_lines") or []

    assert importable == ["Kottbullar med potatismos", "Fiskgratang"]
    assert any(str(item.get("reason") or "") == "heading" for item in ignored)
    assert any(str(item.get("reason") or "") == "alt_marker" for item in ignored)


def test_builder_import_preview_treats_real_dish_rows_as_dish_not_noise(client_admin) -> None:
    lines = [
        "Skottegryta med salt gurka",
        "Isterband med stuvad potatis och rödbetor",
        "Dessert: Exotisk fruktsallad med lättvispad grädde",
    ]
    rv = client_admin.post(
        "/api/builder/import/preview-lines",
        json={"lines": lines},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    preview = (rv.get_json() or {}).get("preview") or {}
    drafts = preview.get("draft_items") or []
    assert len(drafts) == 3
    assert all(str(item.get("item_type") or "") == "dish" for item in drafts)
    assert all(str(item.get("classification") or "") == "importable_dish" for item in drafts)


def test_builder_import_preview_ignores_weekday_and_option_only_rows(client_admin) -> None:
    rv = client_admin.post(
        "/api/builder/import/preview-lines",
        json={"lines": ["Monday", "Vecka 14", "Alt 1", "Alternativ 2", "Lunch", "Fiskgratang"]},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    preview = (rv.get_json() or {}).get("preview") or {}
    ignored = preview.get("ignored_lines") or []
    ignored_texts = {str(item.get("normalized_text") or "") for item in ignored}
    assert "Monday" in ignored_texts
    assert "Vecka 14" in ignored_texts
    assert "Alt 1" in ignored_texts
    assert "Alternativ 2" in ignored_texts
    assert "Lunch" in ignored_texts


def test_builder_import_preview_defaults_select_valid_and_ignore_noise(client_admin) -> None:
    rv = client_admin.post(
        "/api/builder/import/preview-lines",
        json={"lines": ["Alt 1", "Isterband med stuvad potatis och rödbetor", "Potatis"]},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    preview = (rv.get_json() or {}).get("preview") or {}
    drafts = preview.get("draft_items") or []
    assert len(drafts) == 3
    noise = next(item for item in drafts if str(item.get("raw_text") or "") == "Alt 1")
    dish = next(item for item in drafts if "Isterband" in str(item.get("raw_text") or ""))

    assert str(noise.get("item_type") or "") == "ignore"
    assert bool(noise.get("selected")) is False

    assert str(dish.get("item_type") or "") == "dish"
    assert bool(dish.get("selected")) is True
    components = dish.get("components") or []
    component_names = [str(item.get("name") or "") for item in components]
    normalized_names = [name.lower() for name in component_names]
    assert "Isterband" in component_names
    assert any("potatis" in name for name in normalized_names)
