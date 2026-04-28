from __future__ import annotations


def test_menu_output_ui_includes_print_and_export_controls(client_admin) -> None:
    rv = client_admin.get("/menu-output-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Menu Output v1" in html
    assert 'id="menuOutputSelect"' in html
    assert 'id="btnOpenMenuOutput"' in html
    assert 'id="btnPrintMenuOutput"' in html
    assert 'id="btnExportPdfMenuOutput"' in html
    assert 'id="menuOutputTitle"' in html
    assert 'id="menuOutputMeta"' in html
    assert 'id="menuOutputGeneratedAt"' in html
    assert 'id="menuOutputState"' in html
    assert 'id="menuOutputSections"' in html
    assert "Choose a menu above to view a clean printable output." in html
    assert "Print / Save as PDF" in html
    assert "@media print" in html
    assert "@page" in html
    assert ".print-hidden" in html
    assert "display: none !important;" in html


def test_menu_output_script_contains_menu_render_and_print_flow(client_admin) -> None:
    rv = client_admin.get("/static/js/menu_output_v1.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert "function renderSections(rows)" in script
    assert "function fillMenuSelect(menus, selectedMenuId)" in script
    assert "function renderSelectedMenu()" in script
    assert "/api/builder/menus" in script
    assert "/rows" in script
    assert "menu-output-dishes" in script
    assert "No dishes have been added to this menu yet." in script
    assert "Could not load menu rows. Try opening the menu again." in script
    assert "Choose a menu above to view a clean printable output." in script
    assert "Generated: " in script
    assert "window.print()" in script
