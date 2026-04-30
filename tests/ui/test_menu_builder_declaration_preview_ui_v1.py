from __future__ import annotations


def test_menu_builder_ui_shows_create_open_flow_and_hides_technical_identifiers(client_admin) -> None:
    rv = client_admin.get("/menu-builder-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Menu Builder v1.1" in html
    assert "Create or Open Menu" in html
    assert "New menu" in html
    assert "Open existing menu" in html
    assert "Create a menu or open one to start." in html
    assert 'id="btnNewMenu"' in html
    assert 'id="menuTitle"' in html
    assert 'id="menuStartMode"' in html
    assert 'id="btnCreateMenu"' in html
    assert 'id="btnViewPrintActive"' in html
    assert "View / Print menu" in html
    assert "menu_id:" not in html
    assert "week_key" not in html


def test_menu_builder_ui_keeps_template_builder_user_friendly_in_create_flow(client_admin) -> None:
    rv = client_admin.get("/menu-builder-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="menuTemplateWrap"' in html
    assert 'id="menuTemplateType"' in html
    assert 'id="menuTemplateSectionCount"' in html
    assert 'id="menuTemplateSlotCount"' in html
    assert 'id="btnApplyTemplateBuilder"' in html
    assert "What kind of menu?" in html
    assert "How many sections or days?" in html
    assert "How many options per section?" in html
    assert "Create menu structure" in html
    assert 'id="menuTemplateOut"' in html


def test_menu_builder_ui_keeps_sections_slots_and_dish_add_surfaces(client_admin) -> None:
    rv = client_admin.get("/menu-builder-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="newSectionName"' in html
    assert 'id="btnAddSection"' in html
    assert 'id="menuSections"' in html
    assert 'id="menuSectionsOut"' in html
    assert 'id="menuLibraryList"' in html
    assert 'id="btnRefreshMenuLibrary"' in html
    assert 'id="dishPickerModal"' in html
    assert 'id="dishPickerSearch"' in html
    assert 'id="dishPickerSlotMeta"' in html
    assert 'id="dishPickerList"' in html
    assert "Build your menu step by step" in html


def test_menu_builder_script_contains_section_slot_template_and_dish_picker_flow(client_admin) -> None:
    rv = client_admin.get("/static/js/menu_builder_v1.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert "function sectionsFromRows(rows)" in script
    assert "function renameSection(oldName)" in script
    assert "function removeSection(sectionName)" in script
    assert "function generateTemplateStructure()" in script
    assert "function updateTemplateBuilderVisibility()" in script
    assert "function renameSlot(sectionName, slotIndex)" in script
    assert "function addFreeTextDish(sectionName, slotIndex)" in script
    assert "function openDishPicker(sectionName, slotIndex)" in script
    assert "function attachDishToSection(compositionId)" in script
    assert "/api/builder/menus" in script
    assert "/api/builder/compositions" in script
    assert "/api/builder/library" in script
    assert "Choose dish" in script
    assert "Type dish" in script
    assert "Create a menu or open one to start." in script
    assert "btnViewPrintActive" in script
    assert "/menu-output-v1?menu_id=" in script
