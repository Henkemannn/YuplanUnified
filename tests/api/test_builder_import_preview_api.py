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
