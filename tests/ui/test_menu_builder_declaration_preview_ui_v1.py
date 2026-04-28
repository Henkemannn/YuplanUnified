from __future__ import annotations


def test_menu_builder_ui_includes_flexible_section_mvp_controls(client_admin) -> None:
    rv = client_admin.get("/menu-builder-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Menu Builder v1.1" in html
    assert 'id="btnNewMenu"' in html
    assert 'id="menuTitle"' in html
    assert 'id="btnCreateMenu"' in html
    assert 'id="menuTemplateType"' in html
    assert 'id="menuTemplateSectionCount"' in html
    assert 'id="menuTemplateSlotCount"' in html
    assert 'id="btnApplyTemplateBuilder"' in html
    assert 'id="menuTemplateOut"' in html
    assert 'id="newSectionName"' in html
    assert 'id="btnAddSection"' in html
    assert 'id="menuSections"' in html
    assert 'id="menuLibraryList"' in html
    assert 'id="dishPickerModal"' in html
    assert 'id="dishPickerSearch"' in html
    assert 'id="dishPickerSlotMeta"' in html
    assert 'id="dishPickerList"' in html
    assert "No fixed weekdays or Alt slots required." in html


def test_menu_builder_script_contains_section_and_dish_picker_flow(client_admin) -> None:
    rv = client_admin.get("/static/js/menu_builder_v1.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert "function sectionsFromRows(rows)" in script
    assert "function renameSection(oldName)" in script
    assert "function removeSection(sectionName)" in script
    assert "function generateTemplateStructure()" in script
    assert "function renameSlot(sectionName, slotIndex)" in script
    assert "function addFreeTextDish(sectionName, slotIndex)" in script
    assert "function openDishPicker(sectionName, slotIndex)" in script
    assert "function attachDishToSection(compositionId)" in script
    assert "/api/builder/menus" in script
    assert "/api/builder/compositions" in script
    assert "/api/builder/library" in script
    assert "Type new dish" in script
    assert "View/Print" in script
    assert "/menu-output-v1?menu_id=" in script
