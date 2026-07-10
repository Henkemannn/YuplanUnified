from __future__ import annotations


def test_menu_builder_ui_shows_create_open_flow_and_hides_technical_identifiers(client_admin) -> None:
    rv = client_admin.get("/menu-builder-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Skapa meny" in html
    assert 'menu_builder_v1.css' in html
    assert '<style>' not in html
    assert 'id="menuDocumentTitle"' in html
    assert 'id="dishBrowserFilters"' in html
    assert "Ny meny" in html
    assert "Menybibliotek" in html
    assert "Öppna en meny för att fortsätta." in html
    assert 'class="menu-composer-shell menu-composer-grid"' in html
    assert 'class="menu-dish-panel"' in html
    assert 'class="menu-canvas-panel"' in html
    assert 'class="menu-document"' in html
    assert "Rätter" in html
    assert "Sök och välj befintliga rätter till menyn." in html
    assert 'id="btnNewMenu"' in html
    assert 'class="menu-top-action-btn"' in html
    assert 'id="menuTitle"' in html
    assert 'id="btnCreateMenu"' in html
    assert 'class="menu-inline-action-btn"' in html
    assert 'id="btnViewPrintActive"' in html
    assert 'id="btnOpenMenuPanel"' in html
    assert 'href="/builder-workspace-v1"' in html
    assert "Till Builder" in html
    assert "Visa / skriv ut" in html
    assert "Öppna meny" in html
    assert "Öppna en meny för att fortsätta." in html
    assert 'DEBUG MENU TEMPLATE VERSION 2026-07-09' not in html
    assert 'style="' not in html
    assert 'id="dishBrowserSearch"' in html
    assert 'id="dishBrowserList"' in html
    assert "menu_id:" not in html
    assert "week_key" not in html
    assert "Add slot" not in html
    assert "Type dish" not in html
    assert "Option 1" not in html


def test_menu_builder_ui_keeps_template_builder_user_friendly_in_create_flow(client_admin) -> None:
    rv = client_admin.get("/menu-builder-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="menuTemplateWrap"' not in html
    assert 'id="menuTemplateType"' not in html
    assert 'id="menuTemplateSectionCount"' not in html
    assert 'id="menuTemplateSlotCount"' not in html
    assert 'id="btnApplyTemplateBuilder"' not in html
    assert 'id="menuStartMode"' not in html
    assert 'id="menuTemplateOut"' not in html
    assert 'id="btnRefreshSections"' not in html
    assert 'Uppdatera' not in html


def test_menu_builder_ui_keeps_sections_and_dish_add_surfaces(client_admin) -> None:
    rv = client_admin.get("/menu-builder-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="newSectionName"' in html
    assert 'id="btnAddSection"' in html
    assert 'id="menuSections"' in html
    assert 'id="menuSectionsOut"' in html
    assert 'id="menuLibraryList"' in html
    assert 'id="dishBrowserList"' in html
    assert 'id="dishPickerModal"' in html
    assert 'id="dishPickerSearch"' in html
    assert 'id="dishPickerList"' in html
    assert 'id="btnAddSection"' in html
    assert 'id="menuStartWrap"' in html
    assert 'id="dishPickerClose"' in html
    assert "Bygg meny" in html
    assert 'id="dishPickerSlotMeta"' not in html
    assert 'id="btnRefreshSections"' not in html


def test_menu_builder_script_contains_section_slot_template_and_dish_picker_flow(client_admin) -> None:
    rv = client_admin.get("/static/js/menu_builder_v1.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert "function sectionsFromRows(rows)" in script
    assert "function renameSection(oldName)" in script
    assert "function removeSection(sectionName)" in script
    assert "function renameSlot(sectionName, slotIndex)" in script
    assert "function addFreeTextDish(sectionName, slotIndex)" in script
    assert "function openDishPicker(sectionName, slotIndex)" in script
    assert "function attachDishToSection(compositionId)" in script
    assert "/api/builder/menus" in script
    assert "/api/builder/compositions" not in script
    assert "/api/builder/library" in script
    assert "Lägg till" in script
    assert "Lägg till en sektion för att börja bygga menyn." in script
    assert "Direkt skapande av rätt är avstängt i v1A." in script
    assert 'function renderDishBrowser()' in script
    assert 'function renderDishList(host, query, options)' in script
    assert 'const dishBrowserSearch = document.getElementById("dishBrowserSearch");' in script
    assert 'addDishBtn.className = "menu-section-action-btn"' in script
    assert 'renameBtn.className = "menu-section-action-btn"' in script
    assert 'removeBtn.className = "menu-section-action-btn"' in script
    assert 'removeDishBtn.className = "menu-row-remove-btn menu-dish-remove"' in script
    assert 'openBtn.className = "menu-library-action-btn"' in script
    assert 'outputBtn.className = "menu-library-action-btn"' in script
    assert 'removeDishBtn.textContent = "×"' in script
    assert 'removeDishBtn.setAttribute("aria-label", "Ta bort rätt")' in script
    assert 'menu-dish-picker-pill' in script
    assert 'menu-dish-row' in script
    assert "btnViewPrintActive" in script
    assert "/menu-output-v1?menu_id=" in script
