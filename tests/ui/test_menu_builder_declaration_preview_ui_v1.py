from __future__ import annotations


def test_menu_builder_ui_includes_declaration_preview_controls(client_admin) -> None:
    rv = client_admin.get("/menu-builder-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="menuDeclarationVisibleToggle"' in html
    assert 'id="menuDeclarationPreview"' in html
    assert 'id="menuDeclarationStatus"' in html
    assert 'id="menuDeclarationDisabled"' in html
    assert 'id="menuDeclarationSignals"' in html
    assert 'id="menuDeclarationWarnings"' in html
    assert "Read-only preview. No automation applied." in html


def test_menu_builder_script_contains_declaration_preview_toggle_and_warning_rendering(client_admin) -> None:
    rv = client_admin.get("/static/js/menu_builder_v1.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert "menuDeclarationVisibleToggle" in script
    assert "refreshDeclarationPreview" in script
    assert "/declaration-readiness?include_declaration=" in script
    assert "Declaration preview unavailable right now." in script
    assert "Read-only preview. No automation applied." in script
    assert "Row " in script
    assert "No special-diet automation" not in script
