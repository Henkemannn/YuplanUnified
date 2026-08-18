"""
Architecture guard tests for Builder B1 — shared modal extraction.

These tests verify:
1. Builder Workspace includes shared Composition partial.
2. Builder Workspace includes shared Component partial.
3. #resolveModal rendered exactly once.
4. #componentDetailEditorModal rendered exactly once.
5. Shared modal controller JS is loaded.
6. builder.js initializes the shared controller.
7. Modal controller implementation is NOT duplicated in builder.js.
8. Shared controller has repeated-init guard.
9. Dish -> Component -> Dish flow belongs to shared controller.
10. Dish has no recipe/method field.
11. Component has recipe/method.
12. Engine Ownership Contract document exists.
13. Workspace callbacks are explicitly separated.
14. [C1] builder_component_editor.js exists, is loaded before controller, and owns real Component implementation.
15. [C1] builder.js does not contain extracted Component implementation bodies.
16. [C1] controller instantiates component editor via factory.
17. [C1] no builder_modal_runtime.js exists.
"""
from __future__ import annotations

import os
import re


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _workspace_html(client_admin) -> str:
    rv = client_admin.get(
        "/builder-workspace-v1",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert rv.status_code == 200
    return rv.data.decode("utf-8")


def _builder_js(client_admin) -> str:
    rv = client_admin.get("/static/js/builder.js")
    assert rv.status_code == 200
    return rv.data.decode("utf-8")


def _controller_js(client_admin) -> str:
    rv = client_admin.get("/static/js/builder_modal_controller.js")
    assert rv.status_code == 200
    return rv.data.decode("utf-8")


def _component_editor_js(client_admin) -> str:
    rv = client_admin.get("/static/js/builder_component_editor.js")
    assert rv.status_code == 200
    return rv.data.decode("utf-8")


def _dish_editor_js(client_admin) -> str:
    rv = client_admin.get("/static/js/builder_dish_editor.js")
    assert rv.status_code == 200
    return rv.data.decode("utf-8")


def _composition_partial() -> str:
    path = os.path.join("templates", "builder", "_composition_modal.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _component_partial() -> str:
    path = os.path.join("templates", "builder", "_component_detail_modal.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── Guard 1-2: Template includes shared partials ─────────────────────────────


def test_builder_workspace_includes_composition_partial(client_admin) -> None:
    """Builder Workspace renders the shared Composition modal partial."""
    html = _workspace_html(client_admin)
    assert 'id="resolveModal"' in html, "resolveModal not rendered"
    # Template source uses {% include %}
    workspace_path = os.path.join("templates", "builder_workspace_v1.html")
    with open(workspace_path, encoding="utf-8") as f:
        source = f.read()
    assert '{% include "builder/_composition_modal.html" %}' in source


def test_builder_workspace_includes_component_partial(client_admin) -> None:
    """Builder Workspace renders the shared Component detail modal partial."""
    html = _workspace_html(client_admin)
    assert 'id="componentDetailEditorModal"' in html, "componentDetailEditorModal not rendered"
    workspace_path = os.path.join("templates", "builder_workspace_v1.html")
    with open(workspace_path, encoding="utf-8") as f:
        source = f.read()
    assert '{% include "builder/_component_detail_modal.html" %}' in source


# ── Guard 3-4: Single modal instances ────────────────────────────────────────


def test_resolve_modal_rendered_exactly_once(client_admin) -> None:
    """#resolveModal appears exactly once in the rendered HTML."""
    html = _workspace_html(client_admin)
    assert html.count('id="resolveModal"') == 1


def test_component_detail_modal_rendered_exactly_once(client_admin) -> None:
    """#componentDetailEditorModal appears exactly once in the rendered HTML."""
    html = _workspace_html(client_admin)
    assert html.count('id="componentDetailEditorModal"') == 1


# ── Guard 5: Controller script loaded ────────────────────────────────────────


def test_shared_modal_controller_script_loaded(client_admin) -> None:
    """builder_modal_controller.js is served and included before builder.js."""
    html = _workspace_html(client_admin)
    assert 'builder_dish_editor.js' in html, "dish editor script not in template"
    assert 'builder_modal_controller.js' in html, "controller script not in template"
    dish_pos = html.find("builder_dish_editor.js")
    ctrl_pos = html.find("builder_modal_controller.js")
    builder_pos = html.find("builder.js")
    assert dish_pos < ctrl_pos < builder_pos, "dish editor must load before controller, which must load before builder.js"

    rv = client_admin.get("/static/js/builder_dish_editor.js")
    assert rv.status_code == 200
    assert rv.content_type.startswith("application/javascript") or "javascript" in rv.content_type

    rv = client_admin.get("/static/js/builder_modal_controller.js")
    assert rv.status_code == 200
    assert rv.content_type.startswith("application/javascript") or "javascript" in rv.content_type


# ── Guard 6: builder.js initializes the shared controller ────────────────────


def test_builder_js_initializes_shared_controller(client_admin) -> None:
    """builder.js calls createBuilderModalController() to initialize the modal engine."""
    script = _builder_js(client_admin)
    assert "_builderModalController = createBuilderModalController({" in script
    assert "dishEditorFactory: createBuilderDishEditor" in script
    assert "compositionRoot:" in script
    assert "componentRoot:" in script
    assert "initialState: _builderModalShadowState" in script


def test_modal_state_is_owned_by_controller(client_admin) -> None:
    """Modal-local state is stored on the controller instance, not as top-level builder.js declarations."""
    script = _builder_js(client_admin)
    controller = _controller_js(client_admin)

    # Controller owns the modal state container and state accessors.
    assert "const _state = {" in controller
    assert "getState(key)" in controller
    assert "setState(key, value)" in controller
    assert "currentBuilderComposition: null" in controller
    assert "_componentDetailDirty: false" in controller
    assert "getDishEditor()" in controller
    assert "_dishEditor" in controller

    # builder.js no longer declares modal-local state as top-level let bindings.
    assert "let currentBuilderComposition = null;" not in script
    assert "let currentBuilderDishTab = \"overview\";" not in script
    assert "let currentDishAllergenSummaryToken = 0;" not in script
    assert "let currentDishCalculationSummaryToken = 0;" not in script
    assert "let selectedComponentId = null;" not in script
    assert "let pendingComponentCreateForCompositionId = null;" not in script
    assert "let pendingComponentCreateForCompositionName = null;" not in script
    assert "let pendingComponentCreateReturnTab = \"components\";" not in script
    assert "let _activeComponentDetailId = \"\";" not in script
    assert "let _activeComponentDetailTab = \"overview\";" not in script
    assert "let _componentDetailDirty = false;" not in script
    assert "let _componentDetailTagsDraft = [];" not in script


def test_workspace_state_stays_in_builder_js(client_admin) -> None:
    """Builder workspace state remains in builder.js and is not absorbed by the modal controller."""
    script = _builder_js(client_admin)
    controller = _controller_js(client_admin)

    assert "let reusableComponentsCache = [];" in script
    assert "let _workspaceSurface = \"home\";" in script
    assert "let _cachedLibraryComponents = [];" in script
    assert "let _cachedLibraryCompositions = [];" in script
    assert "_workspaceSurface" not in controller
    assert "_cachedLibraryComponents" not in controller
    assert "_cachedLibraryCompositions" not in controller


# ── Guard 7: No duplicate modal implementation in builder.js ─────────────────


def test_modal_controller_not_duplicated_in_builder_js(client_admin) -> None:
    """The modal controller implementation lives only in builder_modal_controller.js."""
    script = _builder_js(client_admin)
    controller = _controller_js(client_admin)

    # createBuilderModalController is DEFINED in controller, not builder.js
    assert "function createBuilderModalController(" in controller
    assert "function createBuilderModalController(" not in script

    # Controller registers its own listeners (not duplicated in builder.js)
    # Tags input keydown handler is in the controller only
    assert 'tagsInput.addEventListener("keydown"' in controller
    assert 'componentDetailTagsInput.addEventListener("keydown"' not in script

    # dishTabButtons listener is in the controller only
    assert 'data-dish-tab]")' in controller or 'data-dish-tab]' in controller
    assert (
        'dishTabButtons.forEach((button) => {' not in script
    ), "dishTabButtons forEach listener must be in controller, not builder.js"


def test_dish_editor_owns_overview_persistence(client_admin) -> None:
    """Dish overview persistence lives in builder_dish_editor.js, not builder.js."""
    script = _builder_js(client_admin)
    dish_editor = _dish_editor_js(client_admin)

    assert "function createBuilderDishEditor(" in dish_editor
    assert "async function saveDishOverviewMetadata()" in dish_editor
    assert "function syncDishModalHeader(composition)" in dish_editor
    assert "function syncDishOverviewInputs(composition)" in dish_editor
    assert "function setDishOverviewStatus(message, isError = false)" in dish_editor
    assert "function dishOverviewCategoryLabel(composition)" in dish_editor
    assert '"/api/builder/compositions/" +' in dish_editor
    assert 'setDishOverviewStatus("Ändringarna sparades.");' in dish_editor
    assert 'showLoading("builderOut");' in dish_editor
    assert 'loadCompositionTextPreviewForCurrentComposition(' in dish_editor

    save_start = script.find("async function saveDishOverviewMetadata() {")
    save_end = script.find("function openBuilderModalForComposition(")
    assert save_start != -1 and save_end != -1 and save_start < save_end
    save_body = script[save_start:save_end]
    assert 'return editor.saveDishOverviewMetadata();' in save_body
    assert '"/api/builder/compositions/" +' not in save_body
    assert 'setDishOverviewStatus("Ändringarna sparades.");' not in save_body
    assert 'showLoading("builderOut");' not in save_body
    assert 'loadCompositionTextPreviewForCurrentComposition(' not in save_body
    assert 'function syncDishModalHeader(composition) {' in script
    assert 'function syncDishOverviewInputs(composition) {' in script
    assert 'function saveDishOverviewMetadata() {' in script


def test_dish_overflow_outside_click_handler_is_controller_owned(client_admin) -> None:
    """The Dish component overflow outside-click handler is registered only by the controller."""
    script = _builder_js(client_admin)
    controller = _controller_js(client_admin)

    assert controller.count('document.addEventListener("click", (event) => {') >= 1
    assert 'const panel = compositionRoot.querySelector("#dishComponentsPanel");' in controller
    assert controller.count('target.closest("#dishComponentsPanel .component-overflow")') >= 1

    assert 'target.closest("#dishComponentsPanel .component-overflow")' not in script


# ── Guard 8: Repeated-init guard prevents double registration ────────────────


def test_shared_controller_has_repeated_init_guard(client_admin) -> None:
    """createBuilderModalController has a guard preventing duplicate listener registration."""
    controller = _controller_js(client_admin)
    assert "_listenersAttached" in controller
    assert "if (_listenersAttached) {" in controller or "if (_listenersAttached)" in controller
    assert "_listenersAttached = true" in controller


# ── Guard 9: Dish → Component → Dish flow in controller ──────────────────────


def test_dish_component_dish_return_flow_in_controller(client_admin) -> None:
    """The Dish → Component → Dish return flow is owned by the controller."""
    controller = _controller_js(client_admin)
    # Controller handles componentDetailReturnToDishBtn
    assert "componentDetailReturnToDishBtn" in controller
    # Controller calls reopenPendingCompositionForReturn (the global)
    assert "reopenPendingCompositionForReturn" in controller
    # Controller calls attachExistingComponentToCurrentComposition
    assert "attachExistingComponentToCurrentComposition" in controller


# ── Guard 10: Dish has no recipe/method field ─────────────────────────────────


def test_dish_modal_has_no_recipe_method_field(client_admin) -> None:
    """The Dish (resolveModal) partial contains no recipe or method fields."""
    partial = _composition_partial()
    assert 'data-dish-tab="recipe"' not in partial
    assert 'data-dish-panel="recipe"' not in partial
    assert 'id="dishOverviewRecipe"' not in partial
    assert "ingredient" not in partial.lower() or "componentDetailRecipeIngredients" not in partial


def test_dish_rendered_modal_has_no_recipe_tab(client_admin) -> None:
    """Rendered Dish modal HTML contains no recipe tab."""
    html = _workspace_html(client_admin)
    resolve_start = html.find('id="resolveModal"')
    add_component_start = html.find('id="addComponentModal"')
    assert resolve_start != -1 and add_component_start != -1
    resolve_html = html[resolve_start:add_component_start]
    assert 'data-dish-tab="recipe"' not in resolve_html
    assert 'data-dish-panel="recipe"' not in resolve_html


# ── Guard 11: Component has recipe/method ─────────────────────────────────────


def test_component_modal_has_recipe_method_tab(client_admin) -> None:
    """The Component detail partial contains recipe/method tab and content."""
    partial = _component_partial()
    assert 'data-component-tab="recipe"' in partial
    assert 'id="componentDetailPanelRecipe"' in partial
    assert 'id="componentDetailMethodText"' in partial
    assert 'id="componentDetailRecipeIngredientRows"' in partial


# ── Guard 12: Engine Ownership Contract exists ────────────────────────────────


def test_engine_ownership_document_exists() -> None:
    """docs/architecture/engine-ownership.md exists and contains required sections."""
    path = os.path.join("docs", "architecture", "engine-ownership.md")
    assert os.path.isfile(path), "engine-ownership.md not found"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "Builder Engine owns" in content
    assert "Planera 2.0 Engine owns" in content
    assert "Business Modules own" in content
    assert "Forbidden" in content
    assert "Mandatory checklist" in content or "Mandatory" in content


# ── Guard 13: Workspace callbacks are explicitly separated ────────────────────


def test_workspace_callbacks_explicitly_separated(client_admin) -> None:
    """The controller receives workspace callbacks through config, not by accessing globals."""
    controller = _controller_js(client_admin)
    script = _builder_js(client_admin)

    # Controller receives loadLibrary as a callback
    assert "loadLibrary:" in controller or "config.loadLibrary" in controller
    # builder.js passes loadLibrary to the controller
    assert "loadLibrary: loadLibrary" in script

    # builder.js passes the Dish editor factory to the controller
    assert "dishEditorFactory: createBuilderDishEditor" in script

    # Controller receives updateComponentCategoryChipCounts as callback
    assert "updateComponentCategoryChipCounts" in controller
    assert "updateComponentCategoryChipCounts: updateComponentCategoryChipCounts" in script

    # Controller should NOT directly call loadLibrary() without going through callbacks
    # (it should use _callbacks.loadLibrary or config.loadLibrary)
    assert "loadLibrary();" not in controller or "_callbacks.loadLibrary" in controller


# ── Guard: Modal CSS is separated for shared consumption ─────────────────────


def test_builder_modal_css_loaded(client_admin) -> None:
    """builder_modal.css is included in the Builder Workspace template."""
    html = _workspace_html(client_admin)
    assert "builder_modal.css" in html

    rv = client_admin.get("/static/css/builder_modal.css")
    assert rv.status_code == 200


def test_builder_modal_css_scoped_to_modal_ids() -> None:
    """builder_modal.css rules are scoped to specific modal IDs, not generic selectors."""
    path = os.path.join("static", "css", "builder_modal.css")
    assert os.path.isfile(path), "builder_modal.css not found"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # Must not contain broad-scope standalone rules
    assert "\n.modal {" not in content, "builder_modal.css must not redefine generic .modal"
    assert "\n.hidden {" not in content, "builder_modal.css must not define standalone .hidden"
    # Must contain scoped rules
    assert "#componentDetailEditorModal" in content
    assert "#dishAllergensPanel" in content or "#dishCalculationPanel" in content


# ── Guard: Modal roots have data-builder-modal-root attribute ─────────────────


def test_modal_roots_have_builder_modal_root_attribute(client_admin) -> None:
    """Both modal roots carry data-builder-modal-root for future CSS scoping."""
    html = _workspace_html(client_admin)
    assert 'data-builder-modal-root="component-detail"' in html
    assert 'data-builder-modal-root="composition"' in html


# ── Guard: Offshore files untouched ──────────────────────────────────────────


def test_offshore_files_not_modified() -> None:
    """No Offshore-owned files were modified by this ticket."""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
    )
    changed = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
    offshore_files = [
        "templates/offshore2/",
        "static/offshore2/",
        "modules/offshore2/",
        "core/offshore_builder_bridge.py",
    ]
    for offshore_path in offshore_files:
        for changed_file in changed:
            assert not changed_file.startswith(offshore_path), (
                f"Offshore file modified: {changed_file}"
            )


# ── Guard C1-1: Component editor file exists and is served ───────────────────


def test_component_editor_script_served(client_admin) -> None:
    """builder_component_editor.js is served and defines createBuilderComponentEditor."""
    editor = _component_editor_js(client_admin)
    assert "function createBuilderComponentEditor(" in editor


def test_component_editor_loaded_before_controller(client_admin) -> None:
    """builder_component_editor.js is loaded before the controller and builder.js."""
    html = _workspace_html(client_admin)
    assert "builder_component_editor.js" in html
    editor_pos = html.find("builder_component_editor.js")
    ctrl_pos = html.find("builder_modal_controller.js")
    builder_pos = html.find("builder.js")
    assert editor_pos < ctrl_pos < builder_pos, (
        "builder_component_editor.js must load before controller, which must load before builder.js"
    )


# ── Guard C1-2: Real Component implementation lives in the editor file ────────


def test_component_editor_owns_real_implementation(client_admin) -> None:
    """The real Component editor behavior lives in builder_component_editor.js."""
    editor = _component_editor_js(client_admin)
    assert "function fetchComponentDetailDraft(componentId)" in editor
    assert '"/api/builder/components/" + encodeURIComponent(idValue) + "/details"' in editor
    assert "function renderRecipeIngredientRows(rows)" in editor
    assert "function syncCalculationRowsFromRecipeRows()" in editor
    assert "function addComponentDetailTagsFromInput(rawValue)" in editor
    assert "function deleteComponentFromLibrary(componentId, componentName)" in editor
    assert "function saveActiveComponentDetailDraft()" in editor
    assert "await _loadLibrary();" in editor
    assert "detail_summary" not in editor
    assert "Recept" in editor or "recipe" in editor.lower()


def test_dish_editor_owns_allergen_status_helpers(client_admin) -> None:
    """The Dish allergen summary helpers live in builder_dish_editor.js."""
    script = _builder_js(client_admin)
    editor = _dish_editor_js(client_admin)

    assert 'const _dishAllergenLabel = typeof config.dishAllergenLabel === "function"' in editor
    assert 'function renderDishAllergenSummary(composition, componentDetails) {' in editor
    assert 'function renderDishAllergenSummaryMessage(message) {' in editor
    assert 'function renderDishAllergenSummaryFailure() {' in editor
    assert 'function renderDishAllergenSummaryEmpty() {' in editor
    assert 'function renderDishAllergenSummaryLoading() {' in editor
    assert 'function renderDishCalculationSummaryMessage(message) {' in editor
    assert 'function renderDishCalculationSummaryFailure() {' in editor
    assert 'function renderDishCalculationSummaryEmpty() {' in editor
    assert 'function renderDishCalculationSummaryLoading() {' in editor
    assert 'function renderDishCalculationRow(row) {' in editor
    assert 'function renderDishCalculationSummary(composition, componentDetails) {' in editor
    assert 'function fetchDishLinkedComponentDetailsForCurrentComposition() {' in editor
    assert 'function loadDishAllergenSummaryForCurrentComposition() {' in editor
    assert 'function loadDishCalculationSummaryForCurrentComposition() {' in editor

    assert 'editor.renderDishAllergenSummaryMessage(message)' in script
    assert 'editor.renderDishAllergenSummaryFailure()' in script
    assert 'editor.renderDishAllergenSummaryEmpty()' in script
    assert 'editor.renderDishAllergenSummaryLoading()' in script
    assert 'function renderDishAllergenSummary(composition, componentDetails) {' in script
    assert 'editor.renderDishAllergenSummary(composition, componentDetails)' in script
    assert 'function fetchDishLinkedComponentDetailsForCurrentComposition() {' in script
    assert 'function loadDishAllergenSummaryForCurrentComposition() {' in script
    assert 'function loadDishCalculationSummaryForCurrentComposition() {' in script


def test_component_editor_owns_recipe_method(client_admin) -> None:
    """Recept & metod implementation lives only in builder_component_editor.js."""
    editor = _component_editor_js(client_admin)
    assert "componentDetailMethodText" in editor
    assert "componentDetailMethodNotes" in editor
    assert "componentDetailRecipeIngredientRows" in editor


# ── Guard C1-3: builder.js does not retain extracted implementation bodies ────


def test_builder_js_no_component_detail_api_bodies(client_admin) -> None:
    """builder.js does not contain the Component detail API persistence bodies."""
    script = _builder_js(client_admin)
    assert '"/api/builder/components/" + encodeURIComponent(idValue) + "/details"' not in script
    assert "normalizeComponentDetailDraft" not in script
    assert "defaultComponentDetailDraft" not in script


def test_builder_js_no_recipe_render_bodies(client_admin) -> None:
    """builder.js does not contain recipe row render or calculation sync bodies."""
    script = _builder_js(client_admin)
    assert "normalizeRecipeIngredientRows" not in script
    assert "parseLegacyRecipeIngredientText" not in script
    assert "recipeIngredientRowsToLegacyText" not in script
    assert "recalculateCalculationRowsCost" not in script
    assert "renderCalculationRows" not in script or "_getBuilderComponentEditor" in script


def test_builder_js_no_tag_implementation(client_admin) -> None:
    """builder.js does not contain Component tag management bodies."""
    script = _builder_js(client_admin)
    assert "parseComponentTagsInput" not in script
    assert "normalizeComponentDetailTagValue" not in script
    assert "renderComponentDetailTagChips" not in script
    assert "setComponentDetailTags" not in script


# ── Guard C1-4: Controller instantiates the component editor via factory ─────


def test_controller_instantiates_component_editor(client_admin) -> None:
    """The controller creates a component editor instance at initialization."""
    controller = _controller_js(client_admin)
    assert "_componentEditorFactory" in controller
    assert "_componentEditor" in controller
    assert "createBuilderComponentEditor" in controller
    assert "getComponentEditor()" in controller


def test_builder_js_passes_editor_factory_to_controller(client_admin) -> None:
    """builder.js passes createBuilderComponentEditor as a factory to the controller."""
    script = _builder_js(client_admin)
    assert "componentEditorFactory: createBuilderComponentEditor" in script
    assert "getCachedComponents: () => _cachedLibraryComponents" in script
    assert "getCachedCompositions: () => _cachedLibraryCompositions" in script


# ── Guard C1-5: No builder_modal_runtime.js ───────────────────────────────────


def test_no_builder_modal_runtime_file() -> None:
    """builder_modal_runtime.js must not exist."""
    assert not os.path.isfile(os.path.join("static", "js", "builder_modal_runtime.js"))


def test_no_builder_modal_runtime_in_template(client_admin) -> None:
    """builder_modal_runtime.js must not appear in the workspace template."""
    html = _workspace_html(client_admin)
    assert "builder_modal_runtime" not in html
