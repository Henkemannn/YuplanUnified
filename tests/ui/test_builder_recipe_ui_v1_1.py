from __future__ import annotations


def test_builder_ui_includes_separate_component_detail_modal_controls(client_admin) -> None:
    rv = client_admin.get("/builder", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="resolveModal"' in html
    assert 'id="componentDetailModal"' in html
    assert 'id="componentDetailModalTitle"' in html
    assert 'id="componentDetailModalClose"' in html
    assert "Component detail" in html
    assert "Recipes for component" in html
    assert 'id="recipeList"' in html
    assert 'id="btnRecipeCreate"' in html
    assert 'id="btnRecipeSetPrimary"' in html
    assert 'id="btnRecipeIngredientAdd"' in html
    assert 'id="recipeIngredientAmountValue"' in html
    assert 'id="recipeIngredientAmountUnit"' in html
    assert 'id="btnRecipeSaveMetadata"' in html
    assert 'id="btnRecipeDelete"' in html
    assert 'id="recipeEditName"' in html
    assert 'id="recipeEditYieldPortions"' in html
    assert 'id="recipeScalingTargetPortions"' in html
    assert 'id="btnRecipeScalingPreview"' in html
    assert 'id="recipeScalingSummary"' in html
    assert 'id="recipeScalingRows"' in html
    assert 'id="componentDeclarationStatus"' in html
    assert 'id="componentDeclarationDisabled"' in html
    assert 'id="componentDeclarationSignals"' in html
    assert 'id="componentConflictList"' in html
    assert 'id="componentDeclarationProvenance"' in html
    assert 'id="componentDeclarationWarnings"' in html

    assert 'id="componentDetailTextPreview"' in html

    resolve_idx = html.find('id="resolveModal"')
    recipe_idx = html.find('id="componentDetailModal"')
    assert resolve_idx != -1
    assert recipe_idx != -1
    assert resolve_idx < recipe_idx

    resolve_html = html[resolve_idx:recipe_idx]
    assert 'id="recipeList"' not in resolve_html
    assert 'id="btnRecipeCreate"' not in resolve_html
    assert 'id="componentDetailTextPreview"' not in resolve_html
    assert 'id="compositionDeclarationStatus"' in resolve_html
    assert 'id="compositionDeclarationSignals"' in resolve_html
    assert 'id="compositionConflictList"' in resolve_html
    assert 'id="compositionDeclarationWarnings"' in resolve_html
    assert "Potential diet conflicts" in html
    assert "Read-only preview. No automation applied." in html


def test_builder_ui_uses_component_block_list_in_dish_editor(client_admin) -> None:
    rv = client_admin.get("/builder", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="builderComponentsList" class="component-block-list"' in html
    assert 'id="builderPaletteSearch"' in html
    assert 'id="builderComponentPalette" class="component-palette"' in html
    assert 'id="manualComponentAddPanel" class="manual-component-panel"' in html


def test_builder_ui_uses_component_cards_in_library_area(client_admin) -> None:
    rv = client_admin.get("/builder", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'id="libraryComponentsGrid" class="component-library-grid"' in html
    assert 'id="libraryComponentsList"' not in html
    assert 'id="libraryCompositionsGrid" class="composition-library-grid"' in html
    assert 'id="libraryCompositionsList"' not in html


def test_builder_script_contains_block_model_and_minimized_controls(client_admin) -> None:
    rv = client_admin.get("/static/js/builder.js")

    assert rv.status_code == 200
    script = rv.data.decode("utf-8")
    assert "component-block" in script
    assert "component-data-icon" in script
    assert "component-overflow-menu" in script
    assert "component-role-input" not in script
    assert "components/reorder" in script
    assert "draggable = true" in script
    assert "dragstart" in script
    assert "drop" in script
    assert "componentDetailModal" in script
    assert "Open component details for this component" in script
    assert "component-library-card" in script
    assert "Open component detail" in script
    assert "openRecipeModalForComponent(componentId, componentName)" in script
    assert "composition-library-card" in script
    assert "Open dish editor" in script
    assert "openCompositionFromLibrary(compositionId)" in script
    assert "component-palette-pill" in script
    assert "component-palette-pill-included" in script
    assert "No components match search" in script
    assert "builderPaletteSearch" in script
    assert "loadComponentDeclarationPreview" in script
    assert "loadCompositionDeclarationPreview" in script
    assert "Declaration preview unavailable right now." in script
    assert "Read-only preview. No automation applied." in script
    assert "componentConflictList" in script
    assert "compositionConflictList" in script
    assert "/components/attach" in script
    assert "attachExistingComponentToCurrentComposition" in script
    assert "/scaling-preview?target_portions=" in script
    assert "Target portions must be > 0" in script
    assert "btnRecipeScalingPreview" in script
