from __future__ import annotations

import re


def test_builder_workspace_v1_route_renders_product_surface(client_admin) -> None:
    rv = client_admin.get("/builder-workspace-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert '<link rel="stylesheet" href="/static/css/builder.css?v=builder-modal-system-reset-1">' in html
    assert "Builder Workspace v1" in html
    assert "Yuplan Builder" in html
    assert "UI foundation v1 active" in html
    assert 'id="builderUiVersionMarker"' in html
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' in html

    # Legacy modal identified in stuck screenshot should be present.
    assert 'id="addComponentModal"' in html
    assert '<p class="workspace-modal-kicker">Dish building</p>' in html
    assert '<h3>Add component</h3>' in html
    assert 'id="addComponentModalClose"' in html

    # Sidebar remains the primary navigation.
    assert 'id="navHomeBtn"' in html
    assert 'id="navComponentsBtn"' in html
    assert 'data-builder-nav="home"' in html
    assert 'data-builder-nav="components"' in html
    assert 'id="navDishesBtn"' in html
    assert 'id="navMenusLink"' in html
    assert 'id="navImportsBtn"' in html
    assert 'id="importsSidebarBadge"' in html

    # Home is action-first and does not render library walls.
    assert 'id="workspaceOverviewSection"' in html
    assert "What do you want to do today?" in html
    assert 'data-action-card="import-menu-recipes"' in html
    assert 'data-action-card="create-component"' in html
    assert 'data-action-card="create-dish"' in html
    assert 'data-action-card="create-menu"' in html
    assert "Import menu or recipe" in html
    assert "Sort components" in html
    assert "Build dishes" in html
    assert "Build menu" in html

    assert 'id="homePendingImportsCount"' in html
    assert 'id="homeUncategorizedComponentsCount"' in html
    assert 'id="homeDishesNeedCategoryCount"' in html
    assert 'id="homeMenusCount"' in html
    assert "Dishes needing review" in html
    assert "Draft menus" in html

    assert 'id="openComponentCreateModalBtn"' in html
    assert 'id="componentsSection" class="builder-library-primary hidden"' in html
    assert 'id="dishesSection" class="builder-library-primary hidden"' in html
    assert 'id="libraryComponentsGrid" class="component-library-grid"' in html
    assert 'id="libraryComponentsCategoryNav"' in html
    assert 'class="builder-components-category-nav"' in html
    assert 'id="libraryComponentsCategoryFilter"' in html
    assert '<option value="all">Alla taggar</option>' in html
    assert "Component library" in html
    assert "Library categories" in html
    assert 'id="componentDetailEditorModal"' in html
    assert html.count('id="componentDetailEditorModal"') == 1
    assert html.count('id="componentDetailEditorTitle"') == 1
    assert html.count('id="componentDetailTabs"') == 1
    assert html.count('id="componentDetailSaveChanges"') == 1
    assert html.count('id="componentDetailEditorClose"') == 1
    assert '<div id="componentDetailEditorModal" class="modal hidden">' in html
    assert 'class="modal-content modal-content-component-detail"' in html
    assert '<h3 id="componentDetailEditorTitle">Komponentredigerare</h3>' in html
    modal_start = html.find('id="componentDetailEditorModal"')
    resolve_start = html.find('id="resolveModal"')
    assert modal_start != -1 and resolve_start != -1 and modal_start < resolve_start
    component_modal_html = html[modal_start:resolve_start]
    assert 'class="modal-content modal-content-component-detail"' in component_modal_html
    assert 'id="componentDetailTabs"' in component_modal_html
    assert 'id="componentDetailModal"' not in html
    assert 'id="componentDetailTabs"' in html
    assert 'data-component-tab="overview"' in html
    assert '>Översikt</button>' in html
    assert 'data-component-tab="recipe"' in html
    assert 'data-component-tab="calculation"' in html
    assert 'data-component-tab="allergens"' in html
    assert 'id="componentDetailTabRecipe"' in html
    assert '📖 Recept &amp; metod' in html
    assert '💰 Kalkyl' in html
    assert '🌾 Allergener/kostinfo' in html
    assert 'id="componentDetailPanelOverview"' in html
    assert 'id="componentDetailPanelRecipe"' in html
    assert 'id="componentDetailPanelCalculation"' in html
    assert 'id="componentDetailPanelAllergens"' in html
    assert html.count('id="componentDetailPanelOverview"') == 1
    assert html.count('id="componentDetailPanelRecipe"') == 1
    assert html.count('id="componentDetailPanelCalculation"') == 1
    assert html.count('id="componentDetailPanelAllergens"') == 1
    assert 'id="componentDetailPanelOverview" class="workspace-modal-section-card component-detail-panel" data-component-panel="overview"' in html
    assert 'id="componentDetailPanelRecipe" class="workspace-modal-section-card component-detail-panel hidden" data-component-panel="recipe"' in html
    assert 'id="componentDetailPanelCalculation" class="workspace-modal-section-card component-detail-panel hidden" data-component-panel="calculation"' in html
    assert 'id="componentDetailPanelAllergens" class="workspace-modal-section-card component-detail-panel hidden" data-component-panel="allergens"' in html
    assert 'id="componentDetailOverviewName"' in html
    assert 'id="componentDetailOverviewClean"' in html
    assert 'id="componentDetailOverviewCategory"' in html
    assert 'Grundinformation' not in html
    assert 'Systeminformation' not in html
    assert 'class="builder-component-overview-stack"' not in html
    assert 'class="builder-component-overview-grid"' in html
    assert 'class="builder-component-overview-card overview-card-identity"' in html
    assert 'class="builder-component-overview-card overview-card-tags"' in html
    assert 'class="builder-component-overview-card overview-card-description"' in html
    assert 'class="builder-component-overview-card overview-card-system"' in html
    assert 'builder-component-overview-field builder-component-overview-field-name' in html
    assert 'builder-component-overview-field builder-component-overview-field-category' in html
    assert 'builder-component-overview-field builder-component-overview-field-tags' in html
    assert 'builder-component-overview-field builder-component-overview-field-description' in html
    assert 'Komponentnamn' in html
    assert 'Rensa namn' in html
    assert 'Rensa amn' not in html
    assert 'Kategori' in html
    assert 'Taggar' in html
    assert 'Beskrivning / längre namn' in html
    assert 'Komponent-ID:' in html
    assert 'Tillbaka till komponenter' in html
    assert 'Category color' not in html
    assert '<option value="main">Huvudkomponent</option>' in html
    assert '<option value="side">Tillbehör</option>' in html
    assert '<option value="sauce">Sås</option>' in html
    assert '<option value="dessert">Dessert</option>' in html
    assert '<option value="ovrigt">Övrigt</option>' in html
    assert '<option value="">Uncategorized</option>' not in html
    assert 'id="componentDetailOverviewTags"' in html
    assert 'id="componentDetailTagsEditor"' in html
    assert 'id="componentDetailTagsChips"' in html
    assert 'id="componentDetailTagsInput"' in html
    assert 'id="componentDetailTagsSuggestions"' in html
    assert 'Tagga för råvara, stil eller sökning.' in html
    assert 'comma-separated' not in html
    assert 'id="componentDetailOverviewLongDescription"' in html
    assert 'id="componentDetailOverviewDelete"' in html
    assert 'class="builder-component-overview-select"' in html
    overview_start = html.find('id="componentDetailPanelOverview"')
    recipe_start = html.find('id="componentDetailPanelRecipe"')
    assert overview_start != -1 and recipe_start != -1 and overview_start < recipe_start
    overview_html = html[overview_start:recipe_start]
    assert overview_html.count('workspace-modal-section-card') == 1
    tags_card_start = overview_html.find('overview-card-tags')
    delete_button_start = overview_html.find('id="componentDetailOverviewDelete"')
    assert tags_card_start != -1
    assert delete_button_start != -1 and delete_button_start > tags_card_start
    assert 'id="componentDetailOverviewColor"' not in html
    assert 'id="componentDetailOverviewSave"' not in html
    assert 'id="componentDetailSaveChanges"' in html
    assert 'id="componentDetailSaveAll"' not in html
    assert 'id="componentDetailOverviewMeta"' in html
    assert 'id="componentDetailRecipeIngredientRows"' in html
    assert 'id="componentDetailRecipeAddRow"' in html
    assert 'class="builder-component-recipe-layout"' in html
    assert 'class="builder-component-recipe-card builder-component-recipe-card-ingredients"' in html
    assert 'class="builder-component-recipe-card builder-component-recipe-card-method"' in html
    assert 'class="builder-component-recipe-header"' in html
    assert 'class="builder-component-recipe-notes-grid"' in html
    assert 'class="builder-component-recipe-note-field"' in html
    assert 'Ingredienser' in html
    assert 'Metod &amp; anteckning' in html
    assert 'Lägg till ingrediens' in html
    assert 'Ingrediens' in html
    assert 'Mängd' in html
    assert 'Enhet' in html
    assert 'Metod' in html
    assert 'Köksanteckning' in html
    assert 'id="componentDetailRecipeIngredients"' in html
    assert 'id="componentDetailMethodText"' in html
    assert 'id="componentDetailMethodNotes"' in html
    assert 'id="componentDetailCalculationRows"' in html
    assert 'id="componentDetailCalcSyncRows"' in html
    assert 'Synka från recept' in html
    assert 'Pris' in html
    assert 'Prisenhet' in html
    assert 'Kostnad' in html
    assert 'Total portionskostnad' in html
    assert 'Kalkylanteckning' in html
    assert 'id="componentDetailCalcYield"' not in html
    assert 'Allergi-/kostanteckning' in html
    assert 'value="gluten_cereals"' in html
    assert 'value="crustaceans"' in html
    assert 'value="eggs"' in html
    assert 'value="fish"' in html
    assert 'value="peanuts"' in html
    assert 'value="soybeans"' in html
    assert 'value="milk_lactose"' in html
    assert 'value="nuts"' in html
    assert 'value="celery"' in html
    assert 'value="mustard"' in html
    assert 'value="sesame"' in html
    assert 'value="sulphur_dioxide_sulphites"' in html
    assert 'value="lupin"' in html
    assert 'value="molluscs"' in html
    assert 'Glutenhaltiga spannmål' in html
    assert 'Kräftdjur' in html
    assert 'Jordnötter' in html
    assert 'Sojabönor' in html
    assert 'Mjölk/laktos' in html
    assert 'Sesamfrön' in html
    assert 'Svaveldioxid och sulfiter' in html
    assert 'Blötdjur' in html
    assert 'value="gluten"' not in html
    assert 'value="milk"' not in html
    assert 'value="egg"' not in html
    assert 'value="soy"' not in html
    assert 'class="builder-platform-layout builder-shell"' in html
    assert 'class="builder-platform-sidebar builder-sidebar"' in html
    assert 'class="builder-platform-primary builder-main"' in html
    assert 'id="libraryCompositionsGrid" class="composition-library-grid"' in html
    assert 'id="libraryDishesSearch"' in html
    assert 'id="libraryDishesScope"' in html
    assert '<option value="needs_component_categories">Needs component categories</option>' in html
    assert '<option value="has_main_component">Has main component</option>' in html
    assert 'id="componentWorkbenchTabs"' not in html
    assert 'id="componentWorkbenchName"' not in html
    assert 'id="componentWorkbenchOverlay"' not in html
    assert 'id="componentWorkbenchPanel"' not in html
    assert 'builder-workbench-overlay' not in html
    assert 'builder-workbench-panel' not in html
    assert 'data-workbench-tab=' not in html

    recipe_panel_start = html.find('id="componentDetailPanelRecipe"')
    calc_panel_start = html.find('id="componentDetailPanelCalculation"')
    assert recipe_panel_start != -1 and calc_panel_start != -1 and recipe_panel_start < calc_panel_start
    recipe_panel_html = html[recipe_panel_start:calc_panel_start]
    assert 'id="componentDetailCalcCost"' not in recipe_panel_html
    assert 'id="componentDetailCalculationRows"' not in recipe_panel_html

    home_start = html.find('id="workspaceOverviewSection"')
    components_start = html.find('id="componentsSection"')
    assert home_start != -1 and components_start != -1 and home_start < components_start
    home_html = html[home_start:components_start]
    action_cards = re.findall(r'data-action-card="[^"]+"', home_html)
    assert len(action_cards) == 4
    assert 'id="libraryComponentsGrid"' not in home_html
    assert 'id="libraryCompositionsGrid"' not in home_html
    home_buttons = re.findall(r"<button[^>]*>", home_html)
    assert home_buttons
    for btn in home_buttons:
        assert "builder-button-" in btn


def test_builder_internal_route_remains_internal_surface(client_admin) -> None:
    rv = client_admin.get("/builder", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Builder Internal UI" in html
    assert "Builder Workspace v1" not in html
    assert 'id="btnImportLibrary"' in html


def test_builder_script_uses_clean_feedback_on_workspace_v1(client_admin) -> None:
    rv = client_admin.get("/static/js/builder.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert 'window.BUILDER_JS_VERSION = "builder-modal-system-reset-1";' in script
    assert 'console.log("Builder JS active: builder-modal-system-reset-1");' in script
    assert 'function resetGlobalModalSafetyState() {' in script
    assert 'document.body.classList.remove("modal-open", "modal-locked");' in script
    assert 'document.documentElement.classList.remove("modal-open", "modal-locked");' in script
    assert 'document.body.style.pointerEvents = "";' in script
    assert 'document.documentElement.style.pointerEvents = "";' in script
    assert 'window.closeComponentWorkbench = closeComponentWorkbench;' not in script
    assert 'componentWorkbench' not in script
    assert 'openComponentWorkbench(' not in script
    assert 'closeComponentWorkbench(' not in script
    assert 'setComponentWorkbenchTab(' not in script
    assert 'data-workbench-tab' not in script

    # Components card contract: clean single-surface tile with direct click-to-open.
    assert 'function cleanComponentInlineName(value)' in script
    assert 'surface.className = "builder-component-card-surface";' in script
    assert 'card.dataset.componentId = componentId;' in script
    assert 'card.dataset.componentTile = "1";' in script
    assert 'surface.dataset.componentId = componentId;' in script
    assert 'surface.dataset.componentTile = "1";' in script
    assert 'surface.dataset.openComponentEditor = "1";' in script
    assert 'surface.appendChild(name);' in script
    assert 'surface.appendChild(badges);' in script
    assert 'const topRow = document.createElement("div");' not in script
    assert 'topRow.className = "component-library-card-row";' not in script
    assert 'surface.addEventListener("click", (event) => {' not in script
    assert 'openComponentDetailEditor(componentId);' in script
    assert 'detailsBtn.textContent = "Open";' not in script
    assert 'popover.className = "builder-component-action-popover";' not in script
    assert 'removeBtn.className = "builder-component-tile-remove";' not in script
    assert 'removeBtn.setAttribute("aria-label", "Remove component");' not in script
    assert 'builder-component-card-body' not in script
    assert 'component-library-card-body' not in script
    assert 'function resolveComponentCategoryThemeKey(item) {' in script
    assert 'const COMPONENT_RAIL_CATEGORY_OPTIONS = ["main", "side", "sauce", "dessert", "ovrigt"];' in script
    assert 'return "Huvudkomponent";' in script
    assert 'return "Tillbehör";' in script
    assert 'return "Sås";' in script
    assert 'return "Övrigt";' in script
    assert '? "Alla"' in script
    assert 'filterKey === "uncategorized" ? "Uncategorized"' not in script
    assert 'return "Main";' not in script
    assert 'return "Side";' not in script
    assert 'return "Sauce";' not in script
    assert 'return "Uncategorized";' not in script
    assert 'card.classList.add("builder-component-card-theme-" + categoryTheme);' in script
    assert 'const detailSummary = componentDetailSummary(item);' in script
    assert 'if (detailSummary.has_method_data) {' in script
    assert 'has_method_data: Boolean(summary && summary.has_method_data === true),' in script
    assert 'if (detailSummary.has_calculation_data) {' in script
    assert 'if (detailSummary.has_allergen_data) {' in script
    assert 'methodIcon.textContent = "📖";' in script
    assert 'methodIcon.title = "Recept/metod finns";' in script
    assert 'calculationIcon.textContent = "💰";' in script
    assert 'calculationIcon.title = "Kalkyl finns";' in script
    assert 'allergenIcon.textContent = "🌾";' in script
    assert 'allergenIcon.title = "Allergen/kostinfo finns";' in script
    assert 'methodIcon.textContent = "M";' not in script
    assert 'calculationIcon.textContent = "C";' not in script
    assert 'allergenIcon.textContent = "A";' not in script
    assert 'allergenIcon.textContent = "⚠️";' not in script
    assert 'allergenIcon.textContent = "⚠";' not in script
    assert 'builder-component-status-icon-method' in script
    assert 'builder-component-status-icon-calculation' in script
    assert 'builder-component-status-icon-allergen' in script
    assert 'categoryBadge.textContent = activeCategory' not in script
    assert 'statusDot.className = "builder-component-status-dot"' not in script
    assert 'const categorySelect = document.createElement("select");' not in script
    assert 'targetGrid.appendChild(card);' in script
    assert 'detail_summary' in script
    assert 'function closeComponentActionPopoverOnly() {' in script
    assert 'componentDetailOverviewCleanBtn' in script
    assert 'componentDetailOverviewDeleteBtn' in script
    assert 'componentDetailOverviewCategoryInput' in script
    assert 'componentDetailRecipeAddRowBtn' in script
    assert 'componentDetailCalcSyncRowsBtn' in script
    assert 'componentDetailSaveChangesBtn' in script
    assert 'window.confirm("Save changes before leaving?")' in script
    assert 'window.confirm("Discard changes and close?")' in script
    assert 'if (modal.id === "componentDetailEditorModal") {' in script
    assert 'await closeComponentDetailEditor();' in script
    assert 'function renderRecipeIngredientRows(rows) {' in script
    assert 'ingredient.placeholder = "Ingrediens";' in script
    assert 'amountValue.placeholder = "Mängd";' in script
    assert 'amountUnit.placeholder = "Enhet (g/ml/dl/kg/l/st)";' in script
    assert 'removeBtn.setAttribute("aria-label", "Ta bort ingrediensrad");' in script
    assert 'function buildCalculationRowsFromRecipeRows(recipeRows, existingCalculationRows) {' in script
    assert 'function syncCalculationRowsFromRecipeRows() {' in script
    assert 'renderCalculationRows(buildCalculationRowsFromRecipeRows(recipeRows, existing));' in script
    assert 'function renderCalculationRows(rows) {' in script
    assert 'priceUnit.placeholder = "Prisenhet (kr/kg, kr/l, kr/st)";' in script
    assert 'calcCost.placeholder = "Kostnad";' in script
    assert 'function recalculateCalculationRowsCost() {' in script
    assert 'removeBtn.className = "builder-row-remove-icon";' in script
    assert 'removeBtn.textContent = "x";' in script
    assert 'removeBtn.textContent = "Remove row";' not in script
    assert 'if (amountUnit === "dl") {' in script
    assert 'if (amountUnit === "g") {' in script
    assert 'actions.appendChild(categorySelect);' not in script
    assert 'const tagRow = document.createElement("div");' not in script
    assert 'builder-tag-row' not in script
    assert 'refs.composition_names' in script
    assert 'await deleteComponentFromLibrary(idValue, componentName);' in script
    assert 'Den här komponenten används i ' in script
    assert 'usedCount === 1 ? " rätt" : " rätter"' in script
    assert 'uniqueDishNames.slice(0, 10)' in script
    assert 'uniqueDishNames.length > 10 ? "\\n- +" + String(uniqueDishNames.length - 10) + " fler" : ""' in script
    assert 'Används i:' in script
    assert 'Nästa steg: öppna berörd rätt för att ta bort eller ersätta komponenten, eller byt namn på komponenten.' in script

    # Home/Components are separate views, not one stacked mixed page.
    assert 'overview.classList.toggle("hidden", _workspaceSurface !== "home");' in script
    assert 'components.classList.toggle("hidden", _workspaceSurface !== "components");' in script
    assert 'function openComponentDetailEditor(componentId) {' in script
    assert 'openSimpleModal("componentDetailEditorModal");' in script
    assert 'openSimpleModal("componentDetailModal");' not in script
    assert 'const libraryComponentsGrid = document.getElementById("libraryComponentsGrid");' in script
    assert 'libraryComponentsGrid.addEventListener("click", (event) => {' in script
    assert 'target.closest("[data-open-component-editor=\'1\']")' in script
    assert 'const componentId = String(trigger.getAttribute("data-component-id") || "").trim();' in script
    assert 'openComponentDetailEditor(componentId);' in script
    assert 'libraryComponentsGrid.addEventListener("keydown", (event) => {' in script
    assert 'keyboardEvent.key !== "Enter" && keyboardEvent.key !== " "' in script
    assert 'target.closest("[data-component-secondary-action=\'1\']")' in script
    assert 'function saveActiveComponentDetailDraft() {' in script
    assert 'const modal = document.getElementById("componentDetailEditorModal");' in script
    assert 'const tabButtons = modal' in script
    assert 'const tabPanels = modal' in script
    assert 'modal.querySelectorAll(".component-detail-panel[data-component-panel]")' in script
    assert 'panel.classList.toggle("hidden", !active);' in script
    assert 'panel.setAttribute("hidden", "hidden");' in script
    assert 'panel.removeAttribute("hidden");' in script
    assert 'function parseComponentTagsInput(value) {' in script
    assert 'function formatComponentTagsInput(tags) {' in script
    assert 'function renderComponentDetailTagChips() {' in script
    assert 'function renderComponentDetailTagSuggestions() {' in script
    assert 'function addComponentDetailTagsFromInput(rawValue) {' in script
    assert 'function removeComponentDetailTag(tagValue) {' in script
    assert 'const componentDetailTagsInput = document.getElementById("componentDetailTagsInput");' in script
    assert 'const componentDetailTagsChips = document.getElementById("componentDetailTagsChips");' in script
    assert 'componentDetailTagsInput.addEventListener("keydown", (event) => {' in script
    assert 'if (event.key !== "Enter" && event.key !== ",") {' in script
    assert 'remove.setAttribute("data-remove-tag", tag);' in script
    assert 'tags: currentComponentDetailTags(),' in script
    assert 'function componentTagCatalog(items) {' in script
    assert 'function renderComponentTagFilterOptions(selectEl, items, activeTag) {' in script
    assert 'const tagFilterSelect = document.getElementById("libraryComponentsCategoryFilter");' in script
    assert 'renderComponentTagFilterOptions(tagFilterSelect, _cachedLibraryComponents, activeTag);' in script
    assert 'const activeTag = currentComponentTagFilter();' in script
    assert 'const componentTags = componentTagValues(item);' in script
    assert 'return componentTags.includes(activeTag);' in script
    assert 'const libraryComponentsCategoryFilterSelect = document.getElementById("libraryComponentsCategoryFilter");' in script
    assert 'libraryComponentsCategoryFilterSelect.addEventListener("change", () => {' in script
    assert 'message.textContent = "Inga komponenter matchar filtret.";' in script
    assert 'const allOption = document.createElement("option");' in script
    assert 'allOption.textContent = "Alla taggar";' in script
    assert 'option.value = tag;' in script
    assert 'option.textContent = tag;' in script
    assert 'const unique = new Set();' in script
    assert 'for (const tag of componentTagValues(item)) {' in script
    assert '.sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }))' in script
    assert '"/api/builder/components/" + encodeURIComponent(idValue) + "/details"' in script
    assert 'method: "GET"' in script
    assert 'method: "PATCH"' in script
    assert 'window.localStorage.setItem(componentDetailStorageKey(idValue), JSON.stringify(payload));' not in script
    assert 'window.localStorage.getItem(key);' not in script
    assert 'setComponentDetailTab(tabValue);' in script
    assert 'closeModalById("componentDetailEditorModal");' in script
    assert 'message: "Komponentdetaljer laddade."' in script
    assert 'message: "Komponentdetaljer sparade."' in script
    assert 'message: "Component details loaded."' not in script
    assert 'message: "Component details saved."' not in script

    assert 'console.error("[modal-open] missing modal", modalId);' in script
    assert 'modal.classList.remove("hidden");' in script
    assert 'modal.removeAttribute("hidden");' in script
    assert 'modal.style.display = "";' in script
    assert 'modal.removeAttribute("aria-hidden");' in script
    assert 'modal.inert = false;' in script
    assert 'const panel = modal.querySelector(".modal-content");' in script
    assert 'panel.classList.remove("hidden");' in script
    assert 'panel.removeAttribute("hidden");' in script
    assert 'panel.style.display = "";' in script
    assert 'panel.removeAttribute("aria-hidden");' in script
    assert 'panel.inert = false;' in script
    assert 'recipe_ingredient_rows: recipeIngredientRows,' in script
    assert 'calculation_rows: normalizeCalculationRows(calculationRows),' in script
    assert 'allergens,' in script

    # Existing builder foundation behavior should still be present.
    assert 'console.info("Builder UI version: foundation-v1");' in script
    assert 'setWorkspaceSurface("home");' in script
    assert 'function setWorkspaceSurface(surface)' in script


def test_builder_component_calculation_examples_contract_values() -> None:
    def _cost(amount_value: float, amount_unit: str, price_value: float, price_unit: str) -> float:
        amount = float(amount_value)
        price = float(price_value)
        unit = str(amount_unit).strip().lower()
        punit = str(price_unit).strip().lower()
        if punit == "kr/kg":
            if unit == "g":
                return (amount / 1000.0) * price
            if unit == "kg":
                return amount * price
        if punit == "kr/l":
            if unit in {"ml", "g"}:
                return (amount / 1000.0) * price
            if unit == "dl":
                return (amount / 10.0) * price
            if unit == "l":
                return amount * price
        if punit == "kr/st" and unit == "st":
            return amount * price
        raise AssertionError("unsupported unit pairing")

    c1 = _cost(80, "g", 22, "kr/kg")
    c2 = _cost(60, "g", 21, "kr/l")
    c3 = _cost(30, "g", 140, "kr/kg")
    total = c1 + c2 + c3

    assert round(c1, 2) == 1.76
    assert round(c2, 2) == 1.26
    assert round(c3, 2) == 4.20
    assert round(total, 2) == 7.22


def test_builder_legacy_modal_close_system_contract(client_admin) -> None:
    rv = client_admin.get("/static/js/builder.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")

    assert 'function closeModalById(id) {' in script
    assert 'modal.classList.add("hidden");' in script
    assert 'modal.style.display = "";' in script
    assert 'modal.removeAttribute("aria-hidden");' in script
    assert 'modal.inert = false;' in script
    assert 'document.body.classList.remove("modal-open", "modal-locked");' in script
    assert 'document.documentElement.classList.remove("modal-open", "modal-locked");' in script

    # Explicit close mappings for all legacy Done/Cancel controls.
    assert 'closeModalById("addComponentModal");' in script
    assert 'closeModalById("importLibraryModal");' in script
    assert 'closeModalById("componentCreateModal");' in script
    assert 'closeModalById("quickCreateModal");' in script
    assert 'closeModalById("dishesLibraryModal");' in script
    assert 'closeModalById("importEditModal");' in script
    assert 'closeModalById("importInboxModal");' in script
    assert 'closeModalById("resolveModal");' in script

    # Emergency close-all support is exposed and invoked at startup.
    assert 'window.closeAllBuilderModals = function () {' in script
    assert 'document.querySelectorAll(".modal").forEach((modal) => {' in script
    assert 'window.closeAllBuilderModals();' in script

    # ESC closes top visible modal and backdrop click closes owning modal.
    assert 'function closeTopVisibleLegacyBuilderModal() {' in script
    assert 'if (event.key !== "Escape") {' in script
    assert 'const didClosePopover = closeComponentActionPopoverOnly();' in script
    assert 'if (didClosePopover) {' in script
    assert 'const didClose = closeTopVisibleLegacyBuilderModal();' in script
    assert 'if (event.target === modal && modal.id) {' in script
    assert 'closeModalById(modal.id);' in script

    # Close path must not set aria-hidden=true.
    assert 'modal.setAttribute("aria-hidden", "true")' not in script


def test_builder_workspace_v1_layout_css_contracts(client_admin) -> None:
    rv = client_admin.get("/static/css/builder.css")

    assert rv.status_code == 200
    css = rv.data.decode("utf-8")

    shell_block = re.search(r"\.builder-shell\s*\{[^}]*\}", css, re.S)
    assert shell_block is not None
    assert "grid-template-columns: 260px minmax(0, 1fr);" in shell_block.group(0)

    sidebar_block = re.search(r"\.builder-sidebar\s*\{[^}]*\}", css, re.S)
    assert sidebar_block is not None
    assert "position: sticky;" in sidebar_block.group(0)
    assert "position: fixed;" not in sidebar_block.group(0)
    assert "z-index: 2;" in sidebar_block.group(0)

    modal_overlay_block = re.search(r"\.builder-workspace-v1 \.modal\s*\{[^}]*\}", css, re.S)
    assert modal_overlay_block is not None
    assert "position: fixed;" in modal_overlay_block.group(0)
    assert "inset: 0;" in modal_overlay_block.group(0)
    assert "z-index: 1200;" in modal_overlay_block.group(0)

    modal_hidden_block = re.search(r"\.builder-workspace-v1 \.modal\.hidden\s*\{[^}]*\}", css, re.S)
    assert modal_hidden_block is not None
    assert "display: none;" in modal_hidden_block.group(0)

    component_modal_overlay_block = re.search(r"\.builder-workspace-v1 #componentDetailEditorModal\.modal\s*\{[^}]*\}", css, re.S)
    assert component_modal_overlay_block is not None
    assert "position: fixed;" in component_modal_overlay_block.group(0)
    assert "inset: 0;" in component_modal_overlay_block.group(0)
    assert "width: 100vw;" in component_modal_overlay_block.group(0)
    assert "height: 100vh;" in component_modal_overlay_block.group(0)
    assert "display: flex;" in component_modal_overlay_block.group(0)
    assert "align-items: flex-start;" in component_modal_overlay_block.group(0)
    assert "justify-content: center;" in component_modal_overlay_block.group(0)
    assert "overflow: auto;" in component_modal_overlay_block.group(0)
    assert "z-index: 1300;" in component_modal_overlay_block.group(0)

    component_modal_hidden_block = re.search(r"\.builder-workspace-v1 #componentDetailEditorModal\.modal\.hidden\s*\{[^}]*\}", css, re.S)
    assert component_modal_hidden_block is not None
    assert "display: none !important;" in component_modal_hidden_block.group(0)

    component_modal_open_block = re.search(r"\.builder-workspace-v1 #componentDetailEditorModal\.modal:not\(\.hidden\)\s*\{[^}]*\}", css, re.S)
    assert component_modal_open_block is not None
    assert "display: flex;" in component_modal_open_block.group(0)
    assert "visibility: visible;" in component_modal_open_block.group(0)
    assert "pointer-events: auto;" in component_modal_open_block.group(0)

    # Final forced override should live after generic workspace modal rules.
    assert css.rfind(".builder-workspace-v1 #componentDetailEditorModal.modal:not(.hidden)") > css.rfind(
        ".builder-workspace-v1 .modal {"
    )
    final_component_modal_open_block = re.search(
        r"\.builder-workspace-v1 #componentDetailEditorModal\.modal:not\(\.hidden\)\s*\{[^}]*!important;[^}]*\}",
        css,
        re.S,
    )
    assert final_component_modal_open_block is not None
    assert "position: fixed !important;" in final_component_modal_open_block.group(0)
    assert "inset: 0 !important;" in final_component_modal_open_block.group(0)
    assert "width: 100vw !important;" in final_component_modal_open_block.group(0)
    assert "height: 100vh !important;" in final_component_modal_open_block.group(0)
    assert "display: flex !important;" in final_component_modal_open_block.group(0)

    final_component_modal_hidden_block = re.search(
        r"\.builder-workspace-v1 #componentDetailEditorModal\.modal\.hidden\s*\{[^}]*\}",
        css,
        re.S,
    )
    assert final_component_modal_hidden_block is not None
    assert "display: none !important;" in final_component_modal_hidden_block.group(0)

    view_hidden_block = re.search(
        r"\.builder-workspace-v1 #workspaceOverviewSection\.hidden,\s*\n\.builder-workspace-v1 #componentsSection\.hidden\s*\{[^}]*\}",
        css,
        re.S,
    )
    assert view_hidden_block is not None
    assert "display: none !important;" in view_hidden_block.group(0)

    modal_panel_block = re.search(r"\.builder-workspace-v1 \.modal-content\s*\{[^}]*\}", css, re.S)
    assert modal_panel_block is not None
    assert "position: relative;" in modal_panel_block.group(0)

    component_modal_panel_block = re.search(
        r"\.builder-workspace-v1 #componentDetailEditorModal \.modal-content-component-detail\s*\{[^}]*\}",
        css,
        re.S,
    )
    assert component_modal_panel_block is not None
    assert "position: relative;" in component_modal_panel_block.group(0)
    assert "width: min(1220px, calc(100vw - 48px));" in component_modal_panel_block.group(0)
    assert "max-height: calc(100vh - 48px);" in component_modal_panel_block.group(0)
    assert "min-height: 320px;" in component_modal_panel_block.group(0)
    assert "overflow: auto;" in component_modal_panel_block.group(0)

    final_component_modal_panel_block = re.search(
        r"\.builder-workspace-v1 #componentDetailEditorModal\.modal:not\(\.hidden\) > \.modal-content-component-detail\s*\{[^}]*!important;[^}]*\}",
        css,
        re.S,
    )
    assert final_component_modal_panel_block is not None
    assert "width: min(1280px, calc(100vw - 48px)) !important;" in final_component_modal_panel_block.group(0)
    assert "min-width: 0 !important;" in final_component_modal_panel_block.group(0)
    assert "min-height: 320px !important;" in final_component_modal_panel_block.group(0)
    assert "max-height: calc(100vh - 48px) !important;" in final_component_modal_panel_block.group(0)
    assert "overflow-x: hidden !important;" in final_component_modal_panel_block.group(0)

    overview_panel_block = re.search(r"#componentDetailPanelOverview:not\(\.hidden\)\s*\{[^}]*\}", css, re.S)
    assert overview_panel_block is not None
    assert "display: grid;" in overview_panel_block.group(0)
    assert "width: 100%;" in overview_panel_block.group(0)
    assert "min-width: 0;" in overview_panel_block.group(0)
    assert "margin: 0;" in overview_panel_block.group(0)
    assert "gap: 10px;" in overview_panel_block.group(0)
    assert "padding: 8px;" in overview_panel_block.group(0)
    assert "--builder-overview-panel-bg:" in overview_panel_block.group(0)
    assert "--builder-overview-card-bg:" in overview_panel_block.group(0)
    assert "--builder-overview-card-border:" in overview_panel_block.group(0)
    assert "--builder-overview-muted-text:" in overview_panel_block.group(0)
    assert "--builder-overview-input-bg:" in overview_panel_block.group(0)
    assert "--builder-overview-input-border:" in overview_panel_block.group(0)
    assert "--builder-overview-card-shadow:" in overview_panel_block.group(0)
    assert "background: var(--builder-overview-panel-bg);" in overview_panel_block.group(0)

    component_hidden_guard_block = re.search(
        r"#componentDetailEditorModal \.component-detail-panel\[hidden\],\s*\n#componentDetailEditorModal \.component-detail-panel\.hidden\s*\{[^}]*\}",
        css,
        re.S,
    )
    assert component_hidden_guard_block is not None
    assert "display: none !important;" in component_hidden_guard_block.group(0)

    assert ".builder-component-overview-stack" not in css

    overview_grid_block = re.search(r"\.builder-component-overview-grid\s*\{[^}]*\}", css, re.S)
    assert overview_grid_block is not None
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in overview_grid_block.group(0)
    assert "gap: 12px;" in overview_grid_block.group(0)

    overview_card_block = re.search(r"\.builder-component-overview-card\s*\{[^}]*\}", css, re.S)
    assert overview_card_block is not None
    assert "border: 1px solid var(--builder-overview-card-border);" in overview_card_block.group(0)
    assert "border-radius: 12px;" in overview_card_block.group(0)
    assert "padding: 10px;" in overview_card_block.group(0)
    assert "background: var(--builder-overview-card-bg);" in overview_card_block.group(0)
    assert "box-shadow: var(--builder-overview-card-shadow);" in overview_card_block.group(0)

    overview_field_block = re.search(r"\.builder-component-overview-field\s*\{[^}]*\}", css, re.S)
    assert overview_field_block is not None
    assert "display: grid;" in overview_field_block.group(0)
    assert "gap: 2px;" in overview_field_block.group(0)

    overview_input_block = re.search(
        r"\.builder-component-overview-field input,\s*\n"
        r"\.builder-component-overview-field select,\s*\n"
        r"\.builder-component-overview-field textarea\s*\{[^}]*\}",
        css,
        re.S,
    )
    assert overview_input_block is not None
    assert "background: var(--builder-overview-input-bg);" in overview_input_block.group(0)
    assert "border-color: var(--builder-overview-input-border);" in overview_input_block.group(0)

    overview_description_block = re.search(r"#componentDetailOverviewLongDescription\s*\{[^}]*\}", css, re.S)
    assert overview_description_block is not None
    assert "min-height: 52px;" in overview_description_block.group(0)
    assert "max-height: 80px;" in overview_description_block.group(0)

    tags_editor_block = re.search(r"\.builder-component-tags-editor\s*\{[^}]*\}", css, re.S)
    assert tags_editor_block is not None
    assert "border: 1px solid var(--builder-overview-input-border);" in tags_editor_block.group(0)
    assert "border-radius: 8px;" in tags_editor_block.group(0)
    assert "padding: 4px;" in tags_editor_block.group(0)
    assert "background: var(--builder-overview-input-bg);" in tags_editor_block.group(0)

    overview_meta_block = re.search(r"\.builder-component-overview-meta\s*\{[^}]*\}", css, re.S)
    assert overview_meta_block is not None
    assert "color: var(--builder-overview-muted-text);" in overview_meta_block.group(0)

    tags_helper_block = re.search(r"\.builder-component-tags-helper\s*\{[^}]*\}", css, re.S)
    assert tags_helper_block is not None
    assert "color: var(--builder-overview-muted-text);" in tags_helper_block.group(0)

    tags_chip_block = re.search(r"\.builder-component-tag-chip\s*\{[^}]*\}", css, re.S)
    assert tags_chip_block is not None
    assert "border-radius: 999px;" in tags_chip_block.group(0)
    assert "font-size: 11px;" in tags_chip_block.group(0)

    tags_chip_remove_block = re.search(r"\.builder-component-tag-chip-remove\s*\{[^}]*\}", css, re.S)
    assert tags_chip_remove_block is not None
    assert "display: inline-flex;" in tags_chip_remove_block.group(0)
    assert "align-items: center;" in tags_chip_remove_block.group(0)
    assert "justify-content: center;" in tags_chip_remove_block.group(0)
    assert "width: 16px;" in tags_chip_remove_block.group(0)
    assert "height: 16px;" in tags_chip_remove_block.group(0)
    assert "line-height: 1;" in tags_chip_remove_block.group(0)
    assert "padding: 0;" in tags_chip_remove_block.group(0)
    assert "border-radius: 999px;" in tags_chip_remove_block.group(0)
    assert "vertical-align: middle;" in tags_chip_remove_block.group(0)

    category_select_block = re.search(r"#componentDetailOverviewCategory\s*\{[^}]*\}", css, re.S)
    assert category_select_block is not None
    assert "min-height: 32px;" in category_select_block.group(0)
    assert "border-radius: 8px;" in category_select_block.group(0)

    overview_mobile_block = re.search(
        r"@media \(max-width: 980px\)\s*\{[^}]*\.builder-component-overview-grid[^}]*grid-template-columns:\s*1fr;",
        css,
        re.S,
    )
    assert overview_mobile_block is not None

    recipe_notes_mobile_block = re.search(
        r"\.builder-component-recipe-notes-grid\s*\{\s*grid-template-columns:\s*1fr;",
        css,
        re.S,
    )
    assert recipe_notes_mobile_block is not None

    tabs_chip_block = re.search(r"\.builder-component-detail-tabs \.builder-chip\s*\{[^}]*\}", css, re.S)
    assert tabs_chip_block is not None
    assert "min-height: 34px;" in tabs_chip_block.group(0)
    assert "gap: 6px;" in tabs_chip_block.group(0)

    tabs_chip_active_block = re.search(r"\.builder-component-detail-tabs \.builder-chip\.is-active\s*\{[^}]*\}", css, re.S)
    assert tabs_chip_active_block is not None
    assert "box-shadow:" in tabs_chip_active_block.group(0)

    assert ".builder-workspace-v1 .modal > .modal-content" in css

    main_block = re.search(r"\.builder-main\s*\{[^}]*\}", css, re.S)
    assert main_block is not None
    assert "width: 100%;" in main_block.group(0)
    assert "min-width: 0;" in main_block.group(0)

    actions_grid_block = re.search(r"\.builder-card-grid-actions\s*\{[^}]*\}", css, re.S)
    assert actions_grid_block is not None
    assert "grid-template-columns: repeat(2, minmax(280px, 1fr));" in actions_grid_block.group(0)

    components_workspace_block = re.search(r"\.builder-components-workspace\s*\{[^}]*\}", css, re.S)
    assert components_workspace_block is not None
    assert "grid-template-columns: 220px minmax(0, 1fr);" in components_workspace_block.group(0)

    component_grid_blocks = re.findall(r"\.builder-workspace-v1 \.component-library-grid\s*\{[^}]*\}", css, re.S)
    assert component_grid_blocks
    assert any("grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));" in block for block in component_grid_blocks)

    compact_card_block = re.search(r"\.builder-component-card-compact\s*\{[^}]*\}", css, re.S)
    assert compact_card_block is not None
    assert "min-height: 40px;" in compact_card_block.group(0)

    card_block = re.search(r"\.builder-component-card\s*\{[^}]*\}", css, re.S)
    assert card_block is not None
    assert "background: #ffffff;" in card_block.group(0)
    assert "min-height: 40px;" in card_block.group(0)
    assert "display: block;" in card_block.group(0)
    assert "--builder-component-accent:" in card_block.group(0)
    assert "--builder-component-border:" in card_block.group(0)
    assert "border: 1px solid var(--builder-component-border);" in card_block.group(0)

    surface_block = re.search(r"\.builder-component-card-surface\s*\{[^}]*\}", css, re.S)
    assert surface_block is not None
    assert "display: grid;" in surface_block.group(0)
    assert "grid-template-columns: minmax(0, 1fr) auto;" in surface_block.group(0)
    assert "min-height: 40px;" in surface_block.group(0)
    assert "background: transparent;" in surface_block.group(0)
    assert "border-radius: 0;" in surface_block.group(0)

    tile_remove_block = re.search(r"\.builder-component-tile-remove\s*\{[^}]*\}", css, re.S)
    assert tile_remove_block is not None
    assert "position: absolute;" in tile_remove_block.group(0)
    assert "top: 50%;" in tile_remove_block.group(0)
    assert "transform: translateY(-50%);" in tile_remove_block.group(0)
    assert "display: inline-flex;" in tile_remove_block.group(0)
    assert "align-items: center;" in tile_remove_block.group(0)
    assert "justify-content: center;" in tile_remove_block.group(0)
    assert "width: 18px;" in tile_remove_block.group(0)
    assert "height: 18px;" in tile_remove_block.group(0)
    assert "opacity: 0;" in tile_remove_block.group(0)
    assert "pointer-events: none;" in tile_remove_block.group(0)

    tile_remove_hover_block = re.search(
        r"\.builder-component-card:hover \.builder-component-tile-remove,\s*\n"
        r"\.builder-component-card:focus-within \.builder-component-tile-remove,\s*\n"
        r"\.builder-component-tile-remove:focus-visible\s*\{[^}]*\}",
        css,
        re.S,
    )
    assert tile_remove_hover_block is not None
    assert "opacity: 1;" in tile_remove_hover_block.group(0)

    # No nested header row style should be required for component tiles.
    assert ".builder-component-card .component-library-card-row" not in css

    surface_hover_block = re.search(r"\.builder-component-card-surface:hover\s*\{[^}]*\}", css, re.S)
    assert surface_hover_block is not None
    assert "background: transparent;" in surface_hover_block.group(0)

    card_strip_block = re.search(r"\.builder-component-card::before\s*\{[^}]*\}", css, re.S)
    assert card_strip_block is not None
    assert "width: 6px;" in card_strip_block.group(0)
    assert "background: var(--builder-component-accent);" in card_strip_block.group(0)

    theme_main_block = re.search(r"\.builder-component-card-theme-main\s*\{[^}]*\}", css, re.S)
    assert theme_main_block is not None
    assert "--builder-component-accent:" in theme_main_block.group(0)
    assert "--builder-component-border: #df8796;" in theme_main_block.group(0)

    theme_fish_block = re.search(r"\.builder-component-card-theme-fish\s*\{[^}]*\}", css, re.S)
    assert theme_fish_block is not None
    assert "--builder-component-accent:" in theme_fish_block.group(0)
    assert "--builder-component-border: #78afd5;" in theme_fish_block.group(0)

    theme_neutral_block = re.search(r"\.builder-component-card-theme-neutral\s*\{[^}]*\}", css, re.S)
    assert theme_neutral_block is not None
    assert "--builder-component-border: #a7b7c7;" in theme_neutral_block.group(0)

    status_icon_block = re.search(r"\.builder-component-status-icon\s*\{[^}]*\}", css, re.S)
    assert status_icon_block is not None
    assert "width: 16px;" in status_icon_block.group(0)

    status_method_block = re.search(r"\.builder-component-status-icon-method\s*\{[^}]*\}", css, re.S)
    assert status_method_block is not None

    status_calc_block = re.search(r"\.builder-component-status-icon-calculation\s*\{[^}]*\}", css, re.S)
    assert status_calc_block is not None

    status_allergen_block = re.search(r"\.builder-component-status-icon-allergen\s*\{[^}]*\}", css, re.S)
    assert status_allergen_block is not None

    calc_rows_block = re.search(r"\.builder-component-calc-rows\s*\{[^}]*\}", css, re.S)
    assert calc_rows_block is not None
    assert "display: grid;" in calc_rows_block.group(0)

    recipe_panel_block = re.search(r"#componentDetailPanelRecipe:not\(\.hidden\)\s*\{[^}]*\}", css, re.S)
    assert recipe_panel_block is not None
    assert "--builder-recipe-panel-bg:" in recipe_panel_block.group(0)
    assert "--builder-recipe-card-bg:" in recipe_panel_block.group(0)
    assert "--builder-recipe-card-border:" in recipe_panel_block.group(0)
    assert "--builder-recipe-input-bg:" in recipe_panel_block.group(0)
    assert "--builder-recipe-input-border:" in recipe_panel_block.group(0)

    recipe_layout_block = re.search(r"\.builder-component-recipe-layout\s*\{[^}]*\}", css, re.S)
    assert recipe_layout_block is not None
    assert "display: grid;" in recipe_layout_block.group(0)
    assert "gap: 12px;" in recipe_layout_block.group(0)

    recipe_card_block = re.search(r"\.builder-component-recipe-card\s*\{[^}]*\}", css, re.S)
    assert recipe_card_block is not None
    assert "border: 1px solid var(--builder-recipe-card-border);" in recipe_card_block.group(0)
    assert "background: var(--builder-recipe-card-bg);" in recipe_card_block.group(0)
    assert "box-shadow: var(--builder-recipe-card-shadow);" in recipe_card_block.group(0)

    recipe_header_block = re.search(r"\.builder-component-recipe-header\s*\{[^}]*\}", css, re.S)
    assert recipe_header_block is not None
    assert "grid-template-columns: minmax(240px, 380px) 80px 70px 32px;" in recipe_header_block.group(0)
    assert "max-width: 720px;" in recipe_header_block.group(0)
    assert "justify-self: start;" in recipe_header_block.group(0)

    recipe_rows_block = re.search(r"\.builder-component-recipe-rows\s*\{[^}]*\}", css, re.S)
    assert recipe_rows_block is not None
    assert "display: grid;" in recipe_rows_block.group(0)
    assert "gap: 6px;" in recipe_rows_block.group(0)
    assert "overflow-x: auto;" in recipe_rows_block.group(0)
    assert "max-width: 720px;" in recipe_rows_block.group(0)
    assert "justify-self: start;" in recipe_rows_block.group(0)

    recipe_row_block = re.search(r"\.builder-component-recipe-row\s*\{[^}]*\}", css, re.S)
    assert recipe_row_block is not None
    assert "grid-template-columns: minmax(240px, 380px) 80px 70px 32px;" in recipe_row_block.group(0)

    recipe_actions_block = re.search(r"\.builder-component-recipe-actions\s*\{[^}]*\}", css, re.S)
    assert recipe_actions_block is not None
    assert "max-width: 720px;" in recipe_actions_block.group(0)
    assert "justify-self: start;" in recipe_actions_block.group(0)

    recipe_row_input_block = re.search(r"\.builder-component-recipe-row input\s*\{[^}]*\}", css, re.S)
    assert recipe_row_input_block is not None
    assert "min-height: 28px;" in recipe_row_input_block.group(0)
    assert "background: var(--builder-recipe-input-bg);" in recipe_row_input_block.group(0)

    recipe_remove_block = re.search(r"\.builder-row-remove-icon\s*\{[^}]*\}", css, re.S)
    assert recipe_remove_block is not None
    assert "width: 22px;" in recipe_remove_block.group(0)
    assert "display: inline-flex;" in recipe_remove_block.group(0)
    assert "align-items: center;" in recipe_remove_block.group(0)
    assert "justify-content: center;" in recipe_remove_block.group(0)

    recipe_remove_center_block = re.search(r"#componentDetailPanelRecipe \.builder-row-remove-icon\s*\{[^}]*\}", css, re.S)
    assert recipe_remove_center_block is not None
    assert "display: inline-flex;" in recipe_remove_center_block.group(0)
    assert "align-items: center;" in recipe_remove_center_block.group(0)
    assert "justify-content: center;" in recipe_remove_center_block.group(0)

    recipe_notes_grid_block = re.search(r"\.builder-component-recipe-notes-grid\s*\{[^}]*\}", css, re.S)
    assert recipe_notes_grid_block is not None
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in recipe_notes_grid_block.group(0)

    recipe_note_textarea_block = re.search(r"\.builder-component-recipe-note-field textarea\s*\{[^}]*\}", css, re.S)
    assert recipe_note_textarea_block is not None
    assert "min-height: 84px;" in recipe_note_textarea_block.group(0)
    assert "max-height: 120px;" in recipe_note_textarea_block.group(0)

    calc_row_block = re.search(r"\.builder-component-calc-row\s*\{[^}]*\}", css, re.S)
    assert calc_row_block is not None
    assert "grid-template-columns: minmax(220px, 1fr) 90px 80px 110px 110px 110px;" in calc_row_block.group(0)

    calc_rows_block = re.search(r"\.builder-component-calc-rows\s*\{[^}]*\}", css, re.S)
    assert calc_rows_block is not None
    assert "overflow-x: auto;" in calc_rows_block.group(0)

    calc_header_block = re.search(r"\.builder-component-grid-head-calc,\s*\n\.builder-component-grid-header-calc\s*\{[^}]*\}", css, re.S)
    assert calc_header_block is not None
    assert "grid-template-columns: minmax(220px, 1fr) 90px 80px 110px 110px 110px;" in calc_header_block.group(0)

    detail_tabs_block = re.search(r"\.builder-component-detail-tabs\s*\{[^}]*\}", css, re.S)
    assert detail_tabs_block is not None
    assert "display: flex;" in detail_tabs_block.group(0)

    allergen_grid_block = re.search(r"\.builder-component-allergen-grid\s*\{[^}]*\}", css, re.S)
    assert allergen_grid_block is not None
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in allergen_grid_block.group(0)

    dish_grid_blocks = re.findall(r"\.builder-workspace-v1 \.composition-library-grid\s*\{[^}]*\}", css, re.S)
    assert dish_grid_blocks
    assert any("grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));" in block for block in dish_grid_blocks)


def test_builder_ui_blueprint_file_exists() -> None:
    from pathlib import Path

    blueprint_path = Path("docs/builder_ui_blueprint.md")
    assert blueprint_path.exists()
    content = blueprint_path.read_text(encoding="utf-8")
    assert "Yuplan Builder UI Blueprint" in content
    assert "fixed left sidebar" in content
    assert "Primary action cards" in content
