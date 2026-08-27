from __future__ import annotations

import re


def test_builder_workspace_v1_route_renders_product_surface(client_admin) -> None:
    rv = client_admin.get("/builder-workspace-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert '<link rel="stylesheet" href="/static/css/builder.css?v=builder-modal-system-reset-1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_modal.css?v=builder-b1-modal-css-v1">' in html
    assert 'builder_editor.css' not in html
    assert "Builder Workspace v1" in html
    assert "Yuplan Builder" in html
    assert "UI foundation v1 active" in html
    assert 'id="builderUiVersionMarker"' in html
    assert '<script src="/static/js/builder_component_editor.js"></script>' in html
    assert '<script src="/static/js/builder_dish_editor.js"></script>' in html
    assert '<script src="/static/js/builder_component_theme.js"></script>' in html
    assert '<script src="/static/js/builder_component_library_runtime.js"></script>' in html
    assert html.count('<script src="/static/js/builder_component_theme.js"></script>') == 1
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' in html
    ce_pos = html.find("builder_component_editor.js")
    de_pos = html.find("builder_dish_editor.js")
    theme_pos = html.find("builder_component_theme.js")
    runtime_pos = html.find("builder_component_library_runtime.js")
    ctrl_pos = html.find("builder_modal_controller.js")
    builder_pos = html.find("builder.js?v=")
    assert ce_pos < de_pos < ctrl_pos < builder_pos
    assert theme_pos < runtime_pos < ce_pos < builder_pos

    # Legacy modal identified in stuck screenshot should be present.
    assert 'id="addComponentModal"' in html
    assert '<p class="workspace-modal-kicker">Dish building</p>' in html
    assert '<h3>Lägg till komponent</h3>' in html
    assert 'id="addComponentModalClose"' in html
    assert 'id="btnAddComponent" type="button">Skapa ny komponent</button>' in html
    assert 'id="newComponentRole"' not in html
    assert 'id="newComponentName"' not in html
    assert 'id="componentRoleSuggestions"' not in html
    assert 'id="componentNameSuggestions"' not in html
    assert 'id="componentDetailReturnToDishBtn"' in html

    # Sidebar remains the primary navigation.
    assert 'id="navHomeBtn"' in html
    assert 'id="navComponentsBtn"' in html
    assert 'data-builder-nav="home"' in html
    assert 'data-builder-nav="components"' in html
    assert 'id="navDishesBtn"' in html
    assert 'id="navMenusLink"' in html
    assert 'id="navImportsBtn"' in html
    assert 'id="importsSidebarBadge"' in html

    assert 'id="libraryDishesCategoryNav"' in html
    assert 'Rättkategorier' in html
    assert 'Rättbibliotek' in html
    assert 'id="libraryDishesSearch"' in html
    assert 'id="dishesBackHomeBtn"' in html
    assert '>Tillbaka<' in html
    assert 'id="openNewDishFromDishesViewBtn"' in html
    assert '>Skapa rätt<' in html

    quick_create_start = html.find('id="quickCreateModal"')
    dishes_library_start = html.find('id="dishesLibraryModal"')
    assert quick_create_start != -1 and dishes_library_start != -1 and quick_create_start < dishes_library_start
    quick_create_html = html[quick_create_start:dishes_library_start]
    assert '<p class="workspace-modal-kicker">Skapa rätt</p>' in quick_create_html
    assert '<h3>Skapa rätt</h3>' in quick_create_html
    assert 'Rättnamn' in quick_create_html
    assert 'id="freeDishName"' in quick_create_html
    assert 'Kategori' in quick_create_html
    assert 'id="freeDishCategory"' in quick_create_html
    assert '<option value="ovrigt" selected>Övrigt</option>' in quick_create_html
    assert '<option value="fisk">Fisk</option>' in quick_create_html
    assert '<option value="kott">Kött</option>' in quick_create_html
    assert '<option value="dessert">Dessert</option>' in quick_create_html
    assert 'id="btnCreateDish" type="button">Skapa rätt</button>' in quick_create_html
    assert 'recipe' not in quick_create_html.lower()
    assert 'calculation' not in quick_create_html.lower()
    assert 'allergen' not in quick_create_html.lower()

    assert 'id="resolveModal"' in html
    resolve_start = html.find('id="resolveModal"')
    add_component_start = html.find('id="addComponentModal"')
    assert resolve_start != -1 and add_component_start != -1 and resolve_start < add_component_start
    resolve_modal_html = html[resolve_start:add_component_start]
    assert 'class="modal-content modal-content-dish modal-content-component-detail"' in resolve_modal_html
    assert 'RÄTTDETALJER' not in resolve_modal_html
    assert 'id="resolveModalTitle"' in resolve_modal_html
    assert 'Redigera rätt' in resolve_modal_html
    assert 'Klar' in resolve_modal_html
    assert 'builder-dish-shell-chips' in resolve_modal_html
    assert 'id="dishOverviewTabBtn" type="button" class="builder-chip is-active" data-dish-tab="overview" aria-pressed="true" aria-selected="true"' in resolve_modal_html
    assert 'id="dishComponentsTabBtn" type="button" class="builder-chip" data-dish-tab="components" aria-pressed="false" aria-selected="false"' in resolve_modal_html
    assert 'id="dishCalculationTabBtn" type="button" class="builder-chip" data-dish-tab="calculation" aria-pressed="false" aria-selected="false"' in resolve_modal_html
    assert 'id="dishAllergensTabBtn" type="button" class="builder-chip" data-dish-tab="allergens" aria-pressed="false" aria-selected="false"' in resolve_modal_html
    assert '🧾 Översikt' in resolve_modal_html
    assert '🧩 Komponentklossar' in resolve_modal_html
    assert '💰 Kalkyl' in resolve_modal_html
    assert '🌾 Allergener/kostinfo' in resolve_modal_html
    assert 'Endast visning' not in resolve_modal_html
    assert 'id="dishOverviewPanel" class="workspace-modal-section-card builder-dish-view-card builder-dish-view-card-overview" data-dish-panel="overview"' in resolve_modal_html
    assert 'id="dishComponentsPanel" class="workspace-modal-section-card builder-dish-view-card builder-dish-view-card-components hidden" data-dish-panel="components" hidden' in resolve_modal_html
    assert 'id="dishCalculationPanel" class="workspace-modal-section-card builder-dish-view-card builder-dish-view-card-calculation hidden" data-dish-panel="calculation" hidden' in resolve_modal_html
    assert 'id="dishAllergensPanel" class="workspace-modal-section-card builder-dish-view-card builder-dish-view-card-allergens hidden" data-dish-panel="allergens" hidden' in resolve_modal_html
    assert 'builder-dish-view-card-overview hidden' not in resolve_modal_html
    assert 'id="dishOverviewName"' in resolve_modal_html
    assert 'id="dishOverviewCategorySelect"' in resolve_modal_html
    assert 'id="dishOverviewUseCustomMenuName"' in resolve_modal_html
    assert 'id="dishOverviewMenuNameField"' in resolve_modal_html
    assert 'id="dishOverviewMenuName"' in resolve_modal_html
    assert 'id="btnDishOverviewSave"' in resolve_modal_html
    assert 'Rättnamn' in resolve_modal_html
    assert 'Kategori' in resolve_modal_html
    assert '<option value="ovrigt">Övrigt</option>' in resolve_modal_html
    assert '<option value="fisk">Fisk</option>' in resolve_modal_html
    assert '<option value="kott">Kött</option>' in resolve_modal_html
    assert '<option value="dessert">Dessert</option>' in resolve_modal_html
    assert 'Använd annat namn i menyer' in resolve_modal_html
    assert 'När detta är av används rättnamnet i menyer och utskrifter.' in resolve_modal_html
    assert 'Menynamn' in resolve_modal_html
    assert 'dishTextPreview' not in resolve_modal_html
    overview_section_start = resolve_modal_html.find('id="dishOverviewPanel"')
    assert overview_section_start != -1
    overview_section_end = resolve_modal_html.find('id="dishComponentsPanel"')
    assert overview_section_end != -1 and overview_section_end > overview_section_start
    overview_section_html = resolve_modal_html[overview_section_start:overview_section_end]
    assert 'id="dishOverviewKlossPreview"' in overview_section_html
    assert 'aria-label="Förhandsvisning komponentklossar"' in overview_section_html
    assert 'id="dishOverviewRecipe"' not in overview_section_html
    assert 'id="dishOverviewCalculation"' not in overview_section_html
    assert 'id="dishOverviewAllergens"' not in overview_section_html
    assert 'id="openAddComponentModalBtn"' not in overview_section_html
    assert 'Lägg till komponent' not in overview_section_html
    assert 'component-overflow' not in overview_section_html
    components_section_start = resolve_modal_html.find('id="dishComponentsPanel"')
    assert components_section_start != -1
    allergens_section_start = resolve_modal_html.find('id="dishAllergensPanel"')
    assert allergens_section_start != -1 and allergens_section_start > components_section_start
    calculation_section_start = resolve_modal_html.find('id="dishCalculationPanel"')
    assert calculation_section_start != -1 and calculation_section_start > allergens_section_start
    components_section_end = calculation_section_start
    assert components_section_end != -1 and components_section_end > components_section_start
    components_section_html = resolve_modal_html[components_section_start:components_section_end]
    assert 'Komponentklossarna bygger upp rätten.' not in components_section_html
    assert 'Lägg till, ta bort och ordna komponentklossarna här.' not in components_section_html
    assert 'Bygg rätten av befintliga komponenter.' in components_section_html
    assert 'Komponenterna som rätten består av.' not in components_section_html
    assert 'id="builderComponentsList"' in components_section_html
    assert 'id="openAddComponentModalBtn"' in components_section_html
    assert 'id="openAddComponentModalBtn" type="button"' in components_section_html
    allergens_section_end = calculation_section_start
    assert allergens_section_end != -1 and allergens_section_end > allergens_section_start
    allergens_section_html = resolve_modal_html[allergens_section_start:allergens_section_end]
    assert 'Sammanställs från rättens komponenter.' in allergens_section_html
    assert 'id="dishAllergensSummary"' in allergens_section_html
    assert 'Inga allergener eller kostmarkörer registrerade på komponenterna.' in allergens_section_html
    assert 'component-detail-allergen-checkbox' not in resolve_modal_html
    assert 'componentDetailAllergenNotes' not in resolve_modal_html
    assert 'data-dish-tab="recipe"' not in resolve_modal_html
    assert 'data-dish-panel="recipe"' not in resolve_modal_html
    assert 'id="dishCalculationSummary"' in resolve_modal_html
    assert 'Sammanställs från rättens komponenter.' in resolve_modal_html
    assert 'id="dishCalculationCost"' not in resolve_modal_html
    assert 'id="dishCalculationNotes"' not in resolve_modal_html
    assert 'id="dishCalculationYield"' not in resolve_modal_html
    assert 'Lägg till komponent' in components_section_html
    assert 'btnCreateDish' not in resolve_modal_html
    assert 'quickCreateModal' not in resolve_modal_html

    js_rv = client_admin.get("/static/js/builder.js")
    assert js_rv.status_code == 200
    js = js_rv.data.decode("utf-8")
    dish_editor_rv = client_admin.get("/static/js/builder_dish_editor.js")
    assert dish_editor_rv.status_code == 200
    dish_editor_js = dish_editor_rv.data.decode("utf-8")
    assert 'Fisk' in js
    assert 'Kött' in js
    assert 'Dessert' in js
    assert 'Övrigt' in js
    render_start = js.find("function renderDishCard(item, targetGrid)")
    derive_preview_start = js.find("function deriveDishCategoryPreview(components)")
    assert render_start != -1 and derive_preview_start != -1 and render_start < derive_preview_start
    render_dish_card_js = js[render_start:derive_preview_start]
    assert 'Reusable composition' not in render_dish_card_js
    assert 'Needs review' not in render_dish_card_js
    assert 'builder-component-card builder-component-card-compact builder-dish-card' in render_dish_card_js
    assert 'builder-component-card-surface builder-dish-card-surface' in render_dish_card_js
    assert 'component-library-card-name builder-dish-card-name' in render_dish_card_js
    assert 'builder-dish-card-actions' not in render_dish_card_js
    assert 'builder-dish-card-open-btn' not in render_dish_card_js
    assert 'builder-dish-card-remove-btn' not in render_dish_card_js
    assert 'Components need review' not in render_dish_card_js
    assert 'Needs component categories' not in render_dish_card_js
    assert 'Behöver översyn' not in render_dish_card_js
    assert 'Inga komponenter ännu' not in render_dish_card_js
    assert '2 komponenter' not in render_dish_card_js
    assert 'componentCountLabel' not in render_dish_card_js
    assert 'status.textContent' not in render_dish_card_js
    assert 'categoryPreview' not in render_dish_card_js
    assert 'Öppna' not in render_dish_card_js
    assert 'Ta bort' not in render_dish_card_js
    assert 'Öppna komponent' in js
    assert 'Ta bort från rätt' in js
    assert 'modalTitle.textContent = String(composition.composition_name || "").trim() || "Redigera rätt";' in js
    assert 'Redigera rätt: ' not in js
    assert 'statusLine.classList.add("hidden");' in js
    assert 'Bygg rätt: ' not in js
    assert 'Justera vad som ska ingå i rätten.' not in js
    assert 'defineBuilderModalStateAccessor("currentBuilderDishTab");' in js
    assert 'function dishBuilderTabValue(value) {' in js
    assert 'if (key === "components" || key === "allergens" || key === "calculation" || key === "overview") {' in js
    assert 'function setDishBuilderTab(tabValue) {' in js
    assert 'panel.hidden = !active;' in js
    assert 'panel.setAttribute("aria-hidden", active ? "false" : "true");' in js
    assert 'if (nextTab === "calculation") {' in js
    assert 'loadDishCalculationSummaryForCurrentComposition().catch(() => {' in js
    assert 'function renderDishOverviewKlossPreview(composition) {' in js
    overview_preview_start = js.find("function renderDishOverviewKlossPreview(composition)")
    overview_preview_end = js.find("function renderBuilderPanel(composition)")
    assert overview_preview_start != -1 and overview_preview_end != -1 and overview_preview_start < overview_preview_end
    overview_preview_js = js[overview_preview_start:overview_preview_end]
    assert 'dishOverviewKlossPreview' in overview_preview_js
    assert 'builder-component-card builder-component-card-compact dish-linked-component-card' in overview_preview_js
    assert 'builder-component-card-surface' in overview_preview_js
    assert 'component-library-card-name' in overview_preview_js
    assert 'component-overflow' not in overview_preview_js
    assert 'openAddComponentModalBtn' not in overview_preview_js
    assert 'data-dish-tab' in js
    assert 'data-dish-panel' in js
    assert 'const VALID_DISH_LIBRARY_GROUPS = new Set(["fisk", "kott", "dessert", "ovrigt"]);' in js
    assert 'function normalizeDishLibraryGroupValue(value) {' in js
    assert 'const normalizeCategoryThemeValue = BuilderComponentTheme.normalizeCategoryThemeValue;' in js
    assert 'function syncDishModalHeader(composition) {' in js
    assert 'function syncDishOverviewInputs(composition) {' in js
    assert 'function renderDishOverview(composition) {' in js
    assert 'function saveDishOverviewMetadata() {' in js
    assert 'renderDishOverview(normalizedComposition);' in js
    assert 'function renderDishAllergenSummary(composition, componentDetails) {' in js
    assert 'function loadDishAllergenSummaryForCurrentComposition() {' in js
    assert 'function fetchDishLinkedComponentDetailsForCurrentComposition() {' in js
    assert 'function renderDishCalculationSummaryMessage(message) {' in js
    assert 'function renderDishCalculationSummaryFailure() {' in js
    assert 'function renderDishCalculationSummaryEmpty() {' in js
    assert 'function renderDishCalculationSummaryLoading() {' in js
    assert 'return editor.renderDishCalculationSummaryMessage(message);' in js or 'editor.renderDishCalculationSummaryMessage(message)' in js
    assert 'return editor.renderDishCalculationSummaryFailure();' in js or 'editor.renderDishCalculationSummaryFailure()' in js
    assert 'return editor.renderDishCalculationSummaryEmpty();' in js or 'editor.renderDishCalculationSummaryEmpty()' in js
    assert 'return editor.renderDishCalculationSummaryLoading();' in js or 'editor.renderDishCalculationSummaryLoading()' in js
    assert 'function renderDishCalculationRow(row) {' in js
    assert 'function renderDishCalculationSummary(composition, componentDetails) {' in js
    assert 'function loadDishCalculationSummaryForCurrentComposition() {' in js
    assert 'function parseDishCurrencyValue(value) {' in dish_editor_js
    assert 'function formatDishCostValue(value) {' in dish_editor_js
    assert 'return value.toFixed(2);' in dish_editor_js
    assert 'formatCostValue(' not in dish_editor_js
    assert 'Saknar kalkyldata' in dish_editor_js
    assert 'Ingen kalkyl registrerad på komponenterna.' in dish_editor_js
    assert 'Komponentkostnad' in dish_editor_js
    assert 'Total kalkyl för rätt' in dish_editor_js
    assert 'Vissa komponenter saknar kalkyldata.' in dish_editor_js
    assert 'formatDishCalculationAmount(' in dish_editor_js
    assert 'formatDishCalculationRowCost(' in dish_editor_js
    assert 'host.insertBefore(totalCard, host.firstChild);' in dish_editor_js
    assert 'const _fetchComponentDetailDraft = typeof config.fetchComponentDetailDraft === "function"' in dish_editor_js
    assert 'await _fetchComponentDetailDraft(componentIdValue);' in dish_editor_js
    assert 'id="dishAllergensPanel"' in html
    assert 'id="dishCalculationPanel"' in html
    assert 'builderCompositionTitle' not in js
    assert 'Rätt: ' not in js
    assert 'function renderDishAllergenSummaryMessage(message) {' in dish_editor_js
    assert 'function renderDishAllergenSummaryFailure() {' in dish_editor_js
    assert 'function renderDishAllergenSummaryEmpty() {' in dish_editor_js
    assert 'function renderDishAllergenSummaryLoading() {' in dish_editor_js
    assert 'function renderDishAllergenSummary(composition, componentDetails) {' in dish_editor_js
    assert 'const _dishAllergenLabel = typeof config.dishAllergenLabel === "function"' in dish_editor_js
    assert 'dishAllergenLabel: dishAllergenLabel' in js
    assert 'function cleanDishTextPreview(text) {' in js
    assert r'replace(/\s*\(component\)/gi, "")' in js
    assert 'const colonIndex = cleaned.indexOf(":");' in js
    assert 'return menuFacing || cleaned;' in js
    assert 'setCompositionTextPreview(targetPreviewId, cleanDishTextPreview(rendered.text));' in js
    builder_panel_start = js.find("function renderBuilderPanel(composition)")
    builder_panel_end = js.find("async function updateComponentRoleInCurrentComposition(componentId, roleValue)")
    assert builder_panel_start != -1 and builder_panel_end != -1 and builder_panel_start < builder_panel_end
    builder_panel_js = js[builder_panel_start:builder_panel_end]
    assert 'builder-component-card builder-component-card-compact dish-linked-component-card' in builder_panel_js
    assert 'builder-component-card-surface' in builder_panel_js
    assert 'component-library-card-name' in builder_panel_js
    assert 'component-overflow' in builder_panel_js
    assert 'card.addEventListener("click", async (event) => {' in builder_panel_js
    assert 'target.closest(".component-row-right")' in builder_panel_js
    assert 'await openComponentDetailEditor(componentIdValue);' in builder_panel_js
    assert 'Öppna komponent' in builder_panel_js
    assert 'Ta bort från rätt' in builder_panel_js
    assert 'function closeDishComponentOverflowMenus(exceptElement = null) {' in js
    assert 'currentDishAllergenSummaryToken += 1;' in js
    assert 'if (currentBuilderDishTab === "allergens") {' in builder_panel_js
    assert 'renderDishAllergenSummaryEmpty();' in builder_panel_js
    assert 'loadDishAllergenSummaryForCurrentComposition().catch(() => {' in builder_panel_js
    assert 'currentDishCalculationSummaryToken += 1;' in js
    assert 'renderDishCalculationSummaryEmpty();' in js
    assert 'loadDishCalculationSummaryForCurrentComposition().catch(() => {' in js
    assert 'target && target.closest(".component-row-right")' in builder_panel_js
    assert 'overflowSummary.addEventListener("click", (event) => {' in builder_panel_js
    assert 'closeDishComponentOverflowMenus(overflow);' in builder_panel_js
    assert 'overflow.addEventListener("toggle", () => {' in builder_panel_js
    assert 'menu.addEventListener("click", (event) => {' in builder_panel_js
    assert 'event.stopPropagation();' in builder_panel_js
    assert 'target.closest("#dishComponentsPanel .component-overflow")' not in js
    assert 'const didCloseDishOverflow = closeDishComponentOverflowMenus();' in js
    assert 'if (nextTab === "allergens") {' in js
    assert 'loadDishAllergenSummaryForCurrentComposition().catch(() => {' in js
    assert 'if (nextTab === "calculation") {' in js
    assert 'loadDishCalculationSummaryForCurrentComposition().catch(() => {' in js
    assert 'Byt namn' not in builder_panel_js
    assert 'Ändra roll' not in builder_panel_js
    assert 'component-role-tag' not in builder_panel_js
    assert 'component-data-icon' in builder_panel_js
    assert 'component-conflict-badge' not in builder_panel_js
    assert 'async function saveDishOverviewMetadata() {' in js
    assert 'const editor = _getBuilderDishEditor();' in js
    assert 'return editor.saveDishOverviewMetadata();' in js

    dish_editor_rv = client_admin.get("/static/js/builder_dish_editor.js")
    assert dish_editor_rv.status_code == 200
    dish_editor_js = dish_editor_rv.data.decode("utf-8")
    assert 'function createBuilderDishEditor(' in dish_editor_js
    assert 'async function saveDishOverviewMetadata() {' in dish_editor_js
    assert '"/api/builder/compositions/" +' in dish_editor_js
    assert 'method: "PATCH"' in dish_editor_js
    assert 'composition_name,' in dish_editor_js
    assert 'library_group,' in dish_editor_js
    assert 'setDishOverviewStatus("");' in dish_editor_js
    assert 'flashDishOverviewSaveButtonSuccess();' in dish_editor_js
    assert 'showJson("builderOut", result);' not in dish_editor_js
    css_rv = client_admin.get("/static/css/builder.css")
    assert css_rv.status_code == 200
    css = css_rv.data.decode("utf-8")
    assert '#resolveModal [data-dish-panel][hidden] {' in css
    assert 'display: none !important;' in css
    assert '.builder-dish-overview-preview-block {' in css
    assert '#dishOverviewKlossPreview {' in css
    assert '#dishOverviewKlossPreview .builder-component-card-surface {' in css
    assert 'pointer-events: none;' in css
    assert '#dishComponentsPanel .component-block-list {' in css
    assert 'overflow-y: visible;' in css
    assert '#dishComponentsPanel .component-overflow {' in css
    assert '#dishComponentsPanel .component-overflow[open] {' in css
    assert '#dishComponentsPanel .component-overflow-menu {' in css
    assert 'position: absolute;' in css
    assert 'top: auto;' in css
    assert 'bottom: calc(100% + 6px);' in css
    assert 'z-index: 60;' in css
    assert 'max-height: 140px;' in css
    assert 'overflow-y: auto;' in css
    assert '#dishComponentsPanel .component-overflow-menu button {' in css
    assert '#dishAllergensPanel .builder-dish-allergen-summary {' in css
    assert '#dishAllergensPanel .builder-dish-allergen-card,' in css
    assert '#dishAllergensPanel .builder-dish-allergen-chip,' in css
    assert '#dishAllergensPanel .builder-dish-allergen-source,' in css
    assert '#dishCalculationPanel .builder-dish-calculation-summary {' in css
    assert '#dishCalculationPanel .builder-dish-calculation-card {' in css
    assert '#dishCalculationPanel .builder-dish-calculation-row {' in css
    assert '#dishCalculationPanel .builder-dish-calculation-total {' in css
    assert '#dishCalculationPanel .builder-dish-calculation-summary-warning {' in css
    dish_list_block = re.search(r"\.builder-dish-view-card \.component-block-list\s*\{[^}]*\}", css, re.S)
    assert dish_list_block is not None
    assert 'gap: 6px;' in dish_list_block.group(0)
    assert '.builder-dish-view-card .dish-linked-component-card {' not in css
    assert '.builder-dish-view-card .dish-linked-component-card .builder-component-card-surface {' not in css
    assert '.builder-dish-view-card .dish-linked-component-card .component-library-card-name {' not in css
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
    assert 'id="componentDetailEditorModal"' in html
    assert 'data-builder-modal-root="component-detail"' in html
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
    assert 'class="builder-component-calc-layout"' in html
    assert 'class="builder-component-calc-card builder-component-calc-card-main"' in html
    assert 'class="builder-component-calc-card builder-component-calc-card-notes"' in html
    assert 'class="builder-component-calc-header builder-component-grid-head builder-component-grid-head-calc"' in html
    assert 'builder-component-calc-actions' in html
    assert 'class="builder-component-calc-total"' in html
    assert 'class="builder-component-calc-note-field"' in html
    assert 'Portionskalkyl' in html
    assert 'Synka från recept' in html
    assert 'Pris' in html
    assert 'Prisenhet' in html
    assert 'Kostnad' in html
    assert 'Total portionskostnad' in html
    assert 'Kalkylanteckning' in html
    assert 'id="componentDetailCalcYield"' not in html
    assert 'class="builder-component-allergen-layout"' in html
    assert 'class="builder-component-allergen-card builder-component-allergen-card-list"' in html
    assert 'class="builder-component-allergen-card builder-component-allergen-card-notes"' in html
    assert 'class="builder-component-allergen-note-field"' in html
    assert 'role="group" aria-label="EU14-allergener"' in html
    assert 'Allergener' in html
    assert 'Kostanteckning' in html
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
    assert 'Ägg' in html
    assert 'Fisk' in html
    assert 'Jordnötter' in html
    assert 'Sojabönor' in html
    assert 'Mjölk/laktos' in html
    assert 'Nötter' in html
    assert 'Selleri' in html
    assert 'Senap' in html
    assert 'Sesamfrön' in html
    assert 'Svaveldioxid och sulfiter' in html
    assert 'Lupin' in html
    assert 'Blötdjur' in html
    assert 'value="gluten"' not in html
    assert 'value="milk"' not in html
    assert 'value="egg"' not in html
    assert 'value="soy"' not in html
    assert 'class="builder-platform-layout builder-shell"' in html
    assert 'class="builder-platform-sidebar builder-sidebar"' in html
    assert 'class="builder-platform-primary builder-main"' in html
    assert 'id="importLibraryModal"' in html
    assert 'id="importContextType"' in html
    assert 'id="importLibraryLines"' in html
    assert 'id="importLibraryFile"' in html
    assert 'id="btnImportLibraryPreview"' in html
    assert 'id="btnImportLibrary"' in html
    assert 'id="btnImportFilePreview"' in html
    assert 'id="btnImportFileConfirm"' in html
    assert 'id="importFilePreviewList"' in html
    assert 'id="importOut"' in html
    assert 'id="importRawInput"' not in html
    assert 'id="importFileInput"' not in html
    assert 'id="libraryCompositionsGrid"' in html
    assert 'builder-dish-library-grid' in html
    assert 'id="libraryDishesSearch"' in html
    assert 'id="libraryDishesCategoryNav"' in html
    assert 'Rättkategorier' in html
    assert 'Rättbibliotek' in html
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
    assert 'function getComponentLibraryRuntime() {' in script
    assert 'BuilderComponentLibraryRuntime.create({' in script
    assert 'getComponentLibraryRuntime().renderPalette();' in script
    assert 'const runtime = BuilderComponentLibraryRuntime.create({' in script
    assert 'const [result] = await Promise.all([' in script
    assert 'callApi("/api/builder/library", { method: "GET" })' in script
    assert 'runtime.loadAllComponents(),' in script
    assert 'renderLibrary(result);' in script
    assert script.index('const [result] = await Promise.all([') < script.index('renderLibrary(result);')
    assert 'function getLibraryComponents() {' in script
    assert 'return getComponentLibraryRuntime().getCachedComponents();' in script
    assert 'const components = getLibraryComponents();' in script
    assert 'renderComponentCategoryFilters(categoryNav, components, activeFilter);' in script
    assert 'renderComponentTagFilterOptions(tagFilterSelect, components, activeTag);' in script
    assert 'const searchFiltered = components.filter((item) => componentMatchesSearch(item, q));' in script
    assert 'const target = getLibraryComponents().find((item) => String(item.component_id || "") === idValue);' in script
    assert 'getComponentLibraryRuntime().upsertCachedComponent(updatedComponent);' in script
    assert 'const palette = document.getElementById("builderComponentPalette");' not in script
    assert 'pill.addEventListener("click", async () => {' not in script
    assert 'openAddComponentModalBtn.addEventListener("click"' not in script
    assert 'addComponentBtn.addEventListener("click"' not in script
    assert 'componentCreateModalCloseBtn.addEventListener("click"' not in script
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
    assert 'BuilderComponentTheme.resolveComponentCategoryThemeKey' in script
    assert 'function resolveComponentCategoryThemeKey(item) {' not in script
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
    assert 'methodIcon.dataset.componentTabTarget = "recipe";' in script
    assert 'methodIcon.setAttribute("role", "button");' in script
    assert 'methodIcon.setAttribute("tabindex", "0");' in script
    assert 'calculationIcon.textContent = "💰";' in script
    assert 'calculationIcon.title = "Kalkyl finns";' in script
    assert 'calculationIcon.dataset.componentTabTarget = "calculation";' in script
    assert 'calculationIcon.setAttribute("role", "button");' in script
    assert 'calculationIcon.setAttribute("tabindex", "0");' in script

    helper_rv = client_admin.get('/static/js/builder_component_theme.js')
    assert helper_rv.status_code == 200
    helper_script = helper_rv.data.decode('utf-8')
    assert 'function resolveComponentCategoryThemeKey(component) {' in helper_script
    assert 'globalThis.BuilderComponentTheme = Object.freeze({' in helper_script
    assert 'allergenIcon.textContent = "🌾";' in script
    assert 'allergenIcon.title = "Allergen/kostinfo finns";' in script
    assert 'allergenIcon.dataset.componentTabTarget = "allergens";' in script
    assert 'allergenIcon.setAttribute("role", "button");' in script
    assert 'allergenIcon.setAttribute("tabindex", "0");' in script
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
    assert 'if (modal.id === "componentDetailEditorModal") {' not in script
    assert 'await closeComponentDetailEditor();' not in script
    assert 'function renderRecipeIngredientRows(rows) {' in script
    assert 'function syncCalculationRowsFromRecipeRows() {' in script
    assert 'deleteComponentFromLibrary' in script
    assert 'actions.appendChild(categorySelect);' not in script
    assert 'const tagRow = document.createElement("div");' not in script
    assert 'builder-tag-row' not in script

    # Home/Components are separate views, not one stacked mixed page.
    assert 'overview.classList.toggle("hidden", _workspaceSurface !== "home");' in script
    assert 'components.classList.toggle("hidden", _workspaceSurface !== "components");' in script
    assert 'openSimpleModal("componentDetailModal");' not in script
    assert 'const libraryComponentsGrid = document.getElementById("libraryComponentsGrid");' in script
    assert 'const importLinesEl = document.getElementById("importLibraryLines");' in script
    assert 'const fileInput = document.getElementById("importLibraryFile");' in script
    assert 'const importLibraryBtn = document.getElementById("btnImportLibrary");' in script
    assert 'const importLibraryPreviewBtn = document.getElementById("btnImportLibraryPreview");' in script
    assert 'const importFilePreviewBtn = document.getElementById("btnImportFilePreview");' in script
    assert 'const importFileConfirmBtn = document.getElementById("btnImportFileConfirm");' in script
    assert 'const importFilePreviewList = document.getElementById("importFilePreviewList");' in script
    assert 'libraryComponentsGrid.addEventListener("click", (event) => {' in script
    assert 'const tabTargetTrigger = target.closest("[data-component-tab-target]");' in script
    assert 'event.stopPropagation();' in script
    assert 'openComponentDetailEditor(componentId, tabTarget);' in script
    assert 'target.closest("[data-open-component-editor=\'1\']")' in script
    assert 'const componentId = String(trigger.getAttribute("data-component-id") || "").trim();' in script
    assert 'openComponentDetailEditor(componentId);' in script
    assert 'libraryComponentsGrid.addEventListener("keydown", (event) => {' in script
    assert 'keyboardEvent.key !== "Enter" && keyboardEvent.key !== " "' in script
    assert 'const tabTarget = componentDetailTabValue(tabTargetTrigger.getAttribute("data-component-tab-target") || "overview");' in script
    assert 'keyboardEvent.stopPropagation();' in script
    assert 'target.closest("[data-component-secondary-action=\'1\']")' in script
    assert 'function saveActiveComponentDetailDraft() {' in script
    assert 'panel.classList.toggle("hidden", !active);' in script
    assert 'panel.setAttribute("hidden", "hidden");' in script
    assert 'panel.removeAttribute("hidden");' in script
    assert 'const componentDetailTagsInput = document.getElementById("componentDetailTagsInput");' in script
    assert 'const componentDetailTagsChips = document.getElementById("componentDetailTagsChips");' in script
    assert 'function componentTagCatalog(items) {' in script
    assert 'function renderComponentTagFilterOptions(selectEl, items, activeTag) {' in script
    assert 'const tagFilterSelect = document.getElementById("libraryComponentsCategoryFilter");' in script
    assert 'const components = getLibraryComponents();' in script
    assert 'renderComponentTagFilterOptions(tagFilterSelect, components, activeTag);' in script
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
    # Component API persistence bodies now live in builder_component_editor.js, not builder.js.
    assert '"/api/builder/components/" + encodeURIComponent(idValue) + "/details"' not in script
    assert 'method: "GET"' in script
    assert 'method: "PATCH"' in script
    assert 'window.localStorage.setItem(componentDetailStorageKey(idValue), JSON.stringify(payload));' not in script
    assert 'window.localStorage.getItem(key);' not in script
    assert 'setComponentDetailTab(' in script
    assert 'closeModalById("componentDetailEditorModal");' in script
    assert 'function openBuilderModalForComposition(composition, initialTab = "overview") {' in script
    assert 'setDishBuilderTab(initialTab);' in script
    assert 'defineBuilderModalStateAccessor("pendingComponentCreateReturnTab");' in script
    assert 'defineBuilderModalStateAccessor("pendingComponentCreateComponentId");' in script
    assert 'function updateComponentDetailReturnAction() {' in script
    assert 'await openComponentDetailEditor(createdComponentId);' in script
    assert 'await attachComponentToPendingComposition(createdComponentId);' not in script
    assert 'pendingComponentCreateComponentId = createdComponentId;' in script
    assert 'if (createdComponentId && pendingComponentCreateForCompositionId && !isDuplicateCreate)' in script
    assert 'isDuplicateCreate = Boolean(result && result.data && result.data.duplicate);' in script
    assert 'openComponentCreateModal: openBuilderComponentCreateModal,' in script
    assert 'clearPendingComponentCreateForComposition();' in script
    assert 'getCachedComponents: () => getComponentLibraryRuntime().getCachedComponents(),' in script
    assert 'resolveComponentById: (componentId) => getComponentLibraryRuntime().resolveComponentById(componentId),' in script
    assert 'getComponentLibraryRuntime().upsertCachedComponent(createdComponent);' in script
    assert 'upsertCachedComponent: (component) => getComponentLibraryRuntime().upsertCachedComponent(component),' in script
    assert '_cachedLibraryComponents' not in script
    assert 'const categoryById = new Map();' in script
    assert 'for (const component of getLibraryComponents()) {' in script
    # Dish return orchestration stays in builder.js; Component editor receives it as a callback.
    assert 'async function reopenPendingCompositionForReturn() {' in script
    assert 'clearPendingComponentCreateForComposition();' in script
    assert 'await loadLibrary();' in script
    assert 'function openBuilderDishCreateModal() {' in script
    assert 'BuilderDishCreateModal.bind({});' in script
    assert 'includeSeedComponents: true' in script
    assert 'createEndpoint: "/api/builder/compositions"' in script or 'createEndpoint: "/api/builder/compositions",' in script
    assert 'openBuilderModalForComposition(composition, "components");' in script
    assert 'freeDishCategoryEl' not in script
    assert 'seed_components: false,' not in script
    assert 'body: { composition_name },' not in script
    assert 'Create dish' not in script
    assert 'Dish creation' not in script
    assert 'Done' not in script

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

    # Existing builder foundation behavior should still be present.
    assert 'console.info("Builder UI version: foundation-v1");' in script
    assert 'setWorkspaceSurface("home");' in script
    assert 'function setWorkspaceSurface(surface)' in script


def test_builder_component_library_runtime_contract(client_admin) -> None:
    rv = client_admin.get("/static/js/builder_component_library_runtime.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert 'globalThis.BuilderComponentLibraryRuntime = Object.freeze({' in script
    assert 'function create(options) {' in script
    assert "'/api/builder/components'" in script
    assert 'const searchValue = getSearchValue().toLowerCase();' in script
    assert "searchInputElement.addEventListener('input'" in script
    assert "button.addEventListener('click', async () => {" in script
    assert 'button.disabled = true;' in script
    assert 'attachedIds.has(componentId)' in script
    assert 'const attachResult = await handleAttach(componentId);' in script
    assert 'async function handleAttach(componentId) {' in script
    assert 'component-palette-pill-included' in script
    assert 'No components match search' in script
    assert 'No reusable components yet' in script


def test_builder_component_editor_sets_category_on_every_open(client_admin) -> None:
    rv = client_admin.get("/static/js/builder_component_editor.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert 'function openComponentDetailEditor(componentId, initialTab) {' in script
    assert 'function clearComponentDetailFeedback() {' in script
    assert 'clearComponentDetailFeedback();' in script
    assert 'Could not save changes.' in script
    assert 'const nextCategory = String(component.category || "").trim().toLowerCase();' in script
    assert 'categoryInput.value = ["main", "side", "sauce", "dessert", "ovrigt"].includes(nextCategory)' in script
    assert 'if (meta) {' in script
    assert 'meta.textContent = "Komponent-ID: " + String(component.component_id || "");' in script


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
    assert 'closeModalById("addComponentModal");' not in script
    assert 'closeModalById("importLibraryModal");' in script
    assert 'closeModalById("componentCreateModal");' not in script
    assert 'function openBuilderDishCreateModal() {' in script
    assert 'includeSeedComponents: true' in script
    assert 'closeModalById("dishesLibraryModal");' in script
    assert 'closeModalById("importEditModal");' in script
    assert 'closeModalById("importInboxModal");' in script
    assert 'closeModalById("resolveModal");' in script

    # Emergency close-all support is exposed and invoked at startup.
    assert 'window.closeAllBuilderModals = function () {' in script
    assert 'document.querySelectorAll(".modal").forEach((modal) => {' in script
    assert 'window.closeAllBuilderModals();' in script

    # ESC closes top visible modal and backdrop click closes owning modal.
    click_block_start = script.find('document.addEventListener("click", (event) => {')
    click_block_end = script.find('document.addEventListener("keydown", (event) => {', click_block_start)
    assert click_block_start != -1 and click_block_end != -1 and click_block_start < click_block_end
    click_block = script[click_block_start:click_block_end]
    assert 'closeTopVisibleLegacyBuilderModal()' not in click_block
    assert 'closeComponentActionPopoverOnly()' in click_block
    assert 'closeDishComponentOverflowMenus()' in click_block
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

    dish_block_list = re.search(r"\.builder-dish-view-card \.component-block-list\s*\{[^}]*\}", css, re.S)
    assert dish_block_list is not None
    assert "background: transparent;" in dish_block_list.group(0)
    assert "border: 0;" in dish_block_list.group(0)
    assert "gap: 6px;" in dish_block_list.group(0)

    dish_block_override = re.search(r"\.builder-dish-view-card \.component-block\s*\{[^}]*\}", css, re.S)
    assert dish_block_override is None

    dish_linked_right_block = re.search(r"\.builder-dish-view-card \.dish-linked-component-card \.component-row-right\s*\{[^}]*\}", css, re.S)
    assert dish_linked_right_block is not None
    assert "align-items: center;" in dish_linked_right_block.group(0)
    assert "gap: 4px;" in dish_linked_right_block.group(0)

    dish_overflow_summary_block = re.search(r"\.builder-dish-view-card \.dish-linked-component-card \.component-overflow summary\s*\{[^}]*\}", css, re.S)
    assert dish_overflow_summary_block is not None
    assert "min-width: 22px;" in dish_overflow_summary_block.group(0)
    assert "min-height: 22px;" in dish_overflow_summary_block.group(0)
    assert "border-radius: 999px;" in dish_overflow_summary_block.group(0)

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

    calc_panel_block = re.search(r"#componentDetailPanelCalculation:not\(\.hidden\)\s*\{[^}]*\}", css, re.S)
    assert calc_panel_block is not None
    assert "--builder-calc-panel-bg:" in calc_panel_block.group(0)
    assert "--builder-calc-card-bg:" in calc_panel_block.group(0)
    assert "--builder-calc-card-border:" in calc_panel_block.group(0)

    calc_layout_block = re.search(r"\.builder-component-calc-layout\s*\{[^}]*\}", css, re.S)
    assert calc_layout_block is not None
    assert "display: grid;" in calc_layout_block.group(0)

    calc_card_block = re.search(r"\.builder-component-calc-card\s*\{[^}]*\}", css, re.S)
    assert calc_card_block is not None
    assert "border: 1px solid var(--builder-calc-card-border);" in calc_card_block.group(0)
    assert "background: var(--builder-calc-card-bg);" in calc_card_block.group(0)
    assert "box-shadow: var(--builder-calc-card-shadow);" in calc_card_block.group(0)

    calc_row_block = re.search(r"\.builder-component-calc-row\s*\{[^}]*\}", css, re.S)
    assert calc_row_block is not None
    assert "grid-template-columns: minmax(220px, 320px) 80px 70px 90px 100px 100px;" in calc_row_block.group(0)

    calc_rows_block = re.search(r"\.builder-component-calc-rows\s*\{[^}]*\}", css, re.S)
    assert calc_rows_block is not None
    assert "overflow-x: auto;" in calc_rows_block.group(0)
    assert "max-width: 920px;" in calc_rows_block.group(0)

    calc_header_block = re.search(r"\.builder-component-grid-head-calc,\s*\n\.builder-component-grid-header-calc\s*\{[^}]*\}", css, re.S)
    assert calc_header_block is not None
    assert "grid-template-columns: minmax(220px, 320px) 80px 70px 90px 100px 100px;" in calc_header_block.group(0)

    calc_total_block = re.search(r"\.builder-component-calc-total\s*\{[^}]*\}", css, re.S)
    assert calc_total_block is not None
    assert "display: grid;" in calc_total_block.group(0)

    calc_cost_block = re.search(r"#componentDetailCalcCost\s*\{[^}]*\}", css, re.S)
    assert calc_cost_block is not None
    assert "font-weight: 800;" in calc_cost_block.group(0)
    assert "font-size: 16px;" in calc_cost_block.group(0)

    detail_tabs_block = re.search(r"\.builder-component-detail-tabs\s*\{[^}]*\}", css, re.S)
    assert detail_tabs_block is not None
    assert "display: flex;" in detail_tabs_block.group(0)

    allergen_panel_block = re.search(r"#componentDetailPanelAllergens:not\(\.hidden\)\s*\{[^}]*\}", css, re.S)
    assert allergen_panel_block is not None
    assert "--builder-allergen-panel-bg:" in allergen_panel_block.group(0)
    assert "--builder-allergen-card-bg:" in allergen_panel_block.group(0)
    assert "--builder-allergen-card-border:" in allergen_panel_block.group(0)

    allergen_layout_block = re.search(r"\.builder-component-allergen-layout\s*\{[^}]*\}", css, re.S)
    assert allergen_layout_block is not None
    assert "display: grid;" in allergen_layout_block.group(0)

    allergen_card_block = re.search(r"\.builder-component-allergen-card\s*\{[^}]*\}", css, re.S)
    assert allergen_card_block is not None
    assert "border: 1px solid var(--builder-allergen-card-border);" in allergen_card_block.group(0)
    assert "background: var(--builder-allergen-card-bg);" in allergen_card_block.group(0)
    assert "box-shadow: var(--builder-allergen-card-shadow);" in allergen_card_block.group(0)

    allergen_grid_block = re.search(r"\.builder-component-allergen-grid\s*\{[^}]*\}", css, re.S)
    assert allergen_grid_block is not None
    assert "grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));" in allergen_grid_block.group(0)

    allergen_chip_block = re.search(r"\.builder-component-allergen-chip span\s*\{[^}]*\}", css, re.S)
    assert allergen_chip_block is not None
    assert "border: 1px solid var(--builder-allergen-input-border);" in allergen_chip_block.group(0)
    assert "background: var(--builder-allergen-input-bg);" in allergen_chip_block.group(0)

    allergen_checked_block = re.search(
        r"\.builder-component-allergen-chip input\[type=\"checkbox\"\]:checked \+ span\s*\{[^}]*\}",
        css,
        re.S,
    )
    assert allergen_checked_block is not None
    assert "border-color:" in allergen_checked_block.group(0)
    assert "background:" in allergen_checked_block.group(0)
    assert "font-weight: 600;" in allergen_checked_block.group(0)

    allergen_notes_block = re.search(r"\.builder-component-allergen-note-field textarea\s*\{[^}]*\}", css, re.S)
    assert allergen_notes_block is not None
    assert "min-height: 78px;" in allergen_notes_block.group(0)
    assert "max-height: 120px;" in allergen_notes_block.group(0)

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
