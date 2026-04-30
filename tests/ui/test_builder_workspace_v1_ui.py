from __future__ import annotations


def test_builder_workspace_v1_route_renders_product_surface(client_admin) -> None:
    rv = client_admin.get("/builder-workspace-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Builder Workspace v1" in html
    assert "Builder library" in html
    assert 'id="openComponentCreateModalBtn"' in html
    assert 'id="openDishesLibraryModalBtn"' in html
    assert 'id="navComponentsBtn"' in html
    assert 'id="navDishesBtn"' in html
    assert 'id="navMenusLink"' in html
    assert 'id="navImportsBtn"' in html
    assert 'id="importsSidebarBadge"' in html
    assert 'id="builderMenusEntry"' in html
    assert 'id="builderImportsInboxSection"' in html
    assert 'id="workspaceOverviewSection"' in html
    assert 'id="workspaceOverviewCards"' in html
    assert 'id="overviewComponentsCount"' in html
    assert 'id="overviewDishesCount"' in html
    assert 'id="overviewMenusCount"' in html
    assert 'id="overviewImportsCount"' in html
    assert 'id="openComponentsViewBtn"' in html
    assert 'id="openDishesViewBtn"' in html
    assert 'id="openMenusViewBtn"' in html
    assert 'id="openImportsViewBtn"' in html
    assert 'id="importsInboxPendingBadge"' in html
    assert 'id="openImportInboxBtn"' in html
    assert 'id="importInboxModal"' in html
    assert 'id="importsInboxList"' in html
    assert 'id="importsInboxCards"' in html
    assert 'id="importAutoSummary"' in html
    assert 'id="btnImportAutoPublish"' in html
    assert 'id="btnImportAutoReviewDetails"' in html
    assert "Create, open, and print menus" in html
    assert "Open Menu Builder" in html
    assert "View/Print Menu" in html
    assert 'id="openNewDishModalBtn"' in html
    assert 'id="openImportModalBtn"' not in html
    assert 'id="componentsSection" class="builder-library-primary hidden"' in html
    assert 'id="libraryComponentsGrid" class="component-library-grid"' in html
    assert 'id="libraryComponentsScope"' in html
    assert '<option value="unused">Unused only</option>' in html
    assert 'id="libraryCompositionsGrid" class="composition-library-grid"' in html
    assert 'id="resolveModal"' in html
    assert 'id="componentDetailModal"' in html
    assert 'id="componentCreateModal"' in html
    assert 'id="quickCreateModal"' in html
    assert 'id="dishesLibraryModal"' in html
    assert 'id="importLibraryModal"' in html
    assert 'id="openAddComponentModalBtn"' in html
    assert 'id="addComponentModal"' in html
    assert 'href="/menu-builder-v1"' in html
    assert 'href="/menu-output-v1"' in html
    assert 'id="btnCreateDish"' in html
    assert 'id="btnCreateComponent"' in html
    assert 'id="btnImportLibrary"' in html
    assert 'id="btnImportLibraryPreview"' in html
    assert 'id="importLibraryLines"' in html
    assert 'id="btnImportFilePreview"' in html
    assert 'id="btnImportFileConfirm"' in html
    assert 'id="importFilePreviewList" class="workspace-import-preview-cards"' in html
    assert 'id="importSummaryView"' in html
    assert 'id="recentImportGroups"' in html
    assert 'id="importEditModal"' in html
    assert 'id="btnImportEditSave"' in html
    assert 'id="importContextType"' in html
    assert 'id="importReviewNotice"' in html
    assert 'id="workspaceDishesMeta"' in html
    assert 'id="workspaceComponentsMeta"' in html
    assert 'id="builderPaletteSearch"' in html
    assert 'id="builderComponentPalette" class="component-palette"' in html
    assert "Builder Internal UI" not in html
    assert "Importera ratter till biblioteket" not in html


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
    assert 'body.classList.contains("builder-workspace-v1")' in script
    assert 'return ok ? "Dish created." : "Could not create dish.";' in script
    assert 'return ok ? "Component created." : "Could not create component.";' in script
    assert 'return ok ? "Saved." : "Could not save changes.";' in script
    assert 'reviewNotice.textContent =' in script
    assert 'possible component matches need review.' in script
    assert 'reviewBlock.className = "import-review-block";' in script
    assert 'const IMPORT_TYPE_MENU = "menu";' in script
    assert 'function parseMenuImportStructure(lines)' in script
    assert 'function createStructuredMenusFromImport(groupedMenu, summary)' in script
    assert 'function suggestionLabelForType(itemType)' in script
    assert 'function openImportEditModal(context, item)' in script
    assert 'function openInlineEdit(source, itemKey, mode, componentIndex)' in script
    assert 'function handleInlineImportEditAction(target)' in script
    assert 'function handleInlineEditKeydown(event)' in script
    assert 'function normalizeImportComponentName(value)' in script
    assert 'function normalizeImportComponentNames(values)' in script
    assert 'function setWorkspaceSurface(surface)' in script
    assert 'function openComponentsSurface() {' in script
    assert 'setWorkspaceSurface("overview");' in script
    assert 'if (_workspaceSurface === "components") {' in script
    assert 'openComponentsViewBtn.addEventListener("click", () => {' in script
    assert 'navComponentsBtn.addEventListener("click", () => {' in script
    assert 'This component is used in ' in script
    assert 'Used by: ' in script
    assert 'editBtn.dataset.inlineAction = "start-card-edit";' in script
    assert 'saveBtn.dataset.inlineAction = "save-card-edit";' in script
    assert 'cancelBtn.dataset.inlineAction = "cancel-inline";' in script
    assert 'removeBtn.dataset.inlineAction = "remove-edit-component";' in script
    assert 'addBtn.dataset.inlineAction = "add-edit-component";' in script
    assert 'toggleBtn.textContent = item.selected ? "Ignore" : "Restore";' in script
    assert 'toggleBtn.textContent = itemData.selected ? "Ignore" : "Restore";' in script
    assert 'if (!editing) {' in script
    assert 'if (String(draft.itemType || "") === "dish") {' in script
    assert 'const compInput = document.createElement("input");' in script
    assert 'await persistInboxItemUpdate(value, item);' in script
    assert 'editChipBtn.dataset.inlineAction = "start-component-edit";' not in script
    assert 'removeChipBtn.dataset.inlineAction = "remove-component";' not in script
    assert 'addComponentBtn.dataset.inlineAction = "start-add-component";' not in script
    assert 'editBtn.textContent = "More";' not in script
    assert 'function isNeedsReviewItem(item)' in script
    assert 'function applyIgnoreObviousNoise()' in script
    assert 'function selectedImportType()' in script
    assert 'function applyComponentLibraryFilter(query)' in script
    assert 'function previewPastedImportLines()' in script
    assert 'const navComponentsBtn = document.getElementById("navComponentsBtn");' in script
    assert 'const navImportsBtn = document.getElementById("navImportsBtn");' in script
    assert 'const openImportInboxBtn = document.getElementById("openImportInboxBtn");' in script
    assert 'openSimpleModal("importInboxModal")' in script
    assert 'appendGroup("Needs review", review' in script
    assert 'appendGroup("Ready to publish", ready' in script
    assert 'appendGroup("Ignored", ignored' in script
    assert 'dataset.reviewAction = "keep"' not in script
    assert '/api/builder/import/preview-lines' in script
    assert 'function loadImportsInboxSessions(preferredSessionId)' in script
    assert '/api/builder/import/sessions' in script
    assert '/publish-selected' in script
    assert 'current.components = itemType === "dish" ? normalizedComponents : [];' in script