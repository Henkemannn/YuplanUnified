from __future__ import annotations

from pathlib import Path


def _headers(*, role: str = "admin", tenant_id: int = 1, user_id: int = 11) -> dict[str, str]:
    return {
        "X-User-Role": role,
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": str(user_id),
    }


def test_builder_editor_host_renders_shared_editor_shell(client_admin) -> None:
    rv = client_admin.get("/builder-editor-host?composition_id=plate_1", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert '<style>' not in html
    assert 'class="builder-workspace-v1 builder-editor-host"' in html
    assert '<link rel="stylesheet" href="/static/css/builder.css?v=builder-modal-system-reset-4">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_modal.css?v=builder-b1-modal-css-v1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_editor_host.css?v=builder-editor-host-v1">' in html
    assert '<script src="/static/js/builder_component_theme.js"></script>' in html
    assert '<script src="/static/js/builder_calculation_utils.js"></script>' in html
    assert '<script src="/static/js/builder_component_library_runtime.js"></script>' in html
    assert '<script src="/static/js/builder_component_editor.js"></script>' in html
    assert '<script src="/static/js/builder_dish_editor.js"></script>' in html
    assert '<script src="/static/js/builder_modal_controller.js?v=builder-b1-modal-controller-v1"></script>' in html
    assert '<script src="/static/js/builder_editor_host.js?v=builder-editor-host-v1"></script>' in html
    assert html.find("builder_component_theme.js") < html.find("builder_calculation_utils.js") < html.find("builder_component_library_runtime.js") < html.find("builder_editor_host.js?v=builder-editor-host-v1")
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' not in html
    assert 'data-rattbibliotek-picker' not in html
    assert 'builder_composition_search.js' not in html
    assert 'builder_dish_create.js' not in html
    assert 'builder-platform-header' not in html
    assert 'builder-shell' not in html
    assert 'builder-sidebar' not in html
    assert 'Tillbaka till matsedeln' not in html
    assert 'builder-editor-host-return' not in html


def test_builder_editor_host_uses_same_assets_for_component_route(client_admin) -> None:
    rv = client_admin.get("/builder-editor-host?component_id=fish", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'class="builder-workspace-v1 builder-editor-host"' in html
    assert '<link rel="stylesheet" href="/static/css/builder.css?v=builder-modal-system-reset-4">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_modal.css?v=builder-b1-modal-css-v1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_editor_host.css?v=builder-editor-host-v1">' in html
    assert '<script src="/static/js/builder_component_theme.js"></script>' in html
    assert '<script src="/static/js/builder_calculation_utils.js"></script>' in html
    assert '<script src="/static/js/builder_component_editor.js"></script>' in html
    assert '<script src="/static/js/builder_dish_editor.js"></script>' in html
    assert '<script src="/static/js/builder_editor_host.js?v=builder-editor-host-v1"></script>' in html
    assert html.find("builder_component_theme.js") < html.find("builder_calculation_utils.js") < html.find("builder_editor_host.js?v=builder-editor-host-v1")
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' not in html
    assert 'Tillbaka till matsedeln' not in html


def test_builder_editor_host_without_target_still_loads_shell(client_admin) -> None:
    rv = client_admin.get("/builder-editor-host", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert '<style>' not in html
    assert 'class="builder-workspace-v1 builder-editor-host"' in html
    assert '<link rel="stylesheet" href="/static/css/builder.css?v=builder-modal-system-reset-4">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_modal.css?v=builder-b1-modal-css-v1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_editor_host.css?v=builder-editor-host-v1">' in html
    assert '<script src="/static/js/builder_component_theme.js"></script>' in html
    assert '<script src="/static/js/builder_calculation_utils.js"></script>' in html
    assert '<script src="/static/js/builder_editor_host.js?v=builder-editor-host-v1"></script>' in html
    assert html.find("builder_component_theme.js") < html.find("builder_calculation_utils.js") < html.find("builder_editor_host.js?v=builder-editor-host-v1")
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' not in html
    assert 'Tillbaka till matsedeln' not in html


def test_builder_editor_host_respects_access_boundary(client_admin) -> None:
    rv = client_admin.get(
        "/builder-editor-host?composition_id=plate_1",
        headers=_headers(role="viewer"),
    )

    assert rv.status_code == 403


def test_builder_editor_host_rejects_picker_and_create_modes(client_admin) -> None:
    for query in ("picker=1", "create=1"):
        rv = client_admin.get("/builder-editor-host?" + query, headers=_headers())
        assert rv.status_code == 400


def test_builder_editor_host_uses_targeted_scoped_reads() -> None:
    host_js = Path("static/js/builder_editor_host.js").read_text(encoding="utf-8")
    controller_js = Path("static/js/builder_modal_controller.js").read_text(encoding="utf-8")

    open_requested_start = host_js.find("async function openRequestedTarget()")
    assert open_requested_start != -1
    open_requested_end = host_js.find("document.addEventListener('DOMContentLoaded'", open_requested_start)
    assert open_requested_end != -1
    open_requested_block = host_js[open_requested_start:open_requested_end]

    assert "await loadLibrary();" not in open_requested_block
    assert "resolveCompositionEditTarget(sourceCompositionId)" in open_requested_block
    assert "loadComponentById(state.componentId)" in open_requested_block
    assert "loadComponentById(" in host_js
    assert "loadCompositionById(" in host_js
    assert "const componentLoadPromises = new Map();" in host_js
    assert "const compositionLoadPromises = new Map();" in host_js
    assert "componentLoadPromises.has(idValue)" in host_js
    assert "componentLoadPromises.set(idValue, loadPromise);" in host_js
    assert "componentLoadPromises.delete(idValue);" in host_js
    assert "compositionLoadPromises.has(idValue)" in host_js
    assert "compositionLoadPromises.set(idValue, loadPromise);" in host_js
    assert "compositionLoadPromises.delete(idValue);" in host_js
    assert "cachedComponents:" not in host_js
    assert "function getCachedComponents() {" not in host_js
    assert "function upsertCachedComponent(component) {" not in host_js
    assert "function renderComponentPalette() {" not in host_js
    assert "BuilderComponentTheme.resolveComponentCategoryThemeKey" in host_js
    assert "function resolveComponentCategoryThemeKey(component) {" not in host_js
    assert "function normalizeCategoryThemeValue(value) {" not in host_js
    assert "const resolveComponentCategoryThemeKey = BuilderComponentTheme.resolveComponentCategoryThemeKey;" in host_js
    assert "async function resolveComponentById(componentId)" not in host_js
    assert "function resolveComponentById(componentId)" in host_js
    assert "async function preloadLinkedComponents(composition)" in host_js
    assert "resolveCompositionEditTarget(" in host_js
    assert "'/api/builder/compositions/' + encodeURIComponent(idValue) + '/edit-target'" in host_js
    assert "const sourceCompositionId = state.compositionId;" in host_js
    assert "const editableComposition = await resolveCompositionEditTarget(sourceCompositionId);" in host_js
    assert "state.compositionId = editableComposition.composition_id;" in host_js
    assert "await preloadLinkedComponents(editableComposition);" in host_js
    assert "state.hostTargetId = editableComposition.composition_id;" not in host_js
    assert "state.controller.openComposition(editableComposition, 'overview');" in host_js
    assert "notifyHostRuntimeReady();" in host_js
    assert "builder-host-ping" in host_js
    assert "builder-host-open" in host_js
    assert "builder-host-runtime-ready" in host_js
    assert "prepareLinkedComponentForEdit" in host_js
    assert "'/api/builder/compositions/' + encodeURIComponent(compositionId) + '/components/' + encodeURIComponent(sourceComponentId) + '/edit-target'" in host_js
    assert "upsertCachedComponent(result.data.component);" in host_js
    assert "upsertCachedComposition(result.data.composition);" in host_js
    assert "const component = await loadComponentById(state.componentId);" in host_js
    assert "await state.controller.openComponentDetailEditor(component.component_id, 'overview');" in host_js
    assert "searchInputElement.addEventListener('input'" not in host_js
    assert "button.addEventListener('click', async () => {" not in host_js
    assert "prepareLinkedComponentForEdit" in controller_js
    assert "syncDishMenuNameVisibility" in controller_js
    assert "dishOverviewUseCustomMenuName" in controller_js
    assert "dishOverviewMenuName" in controller_js
    assert "_openLinkedComponentEditor" in controller_js
    assert "await _openLinkedComponentEditor(componentIdValue);" in controller_js
    assert "openComponentDetailEditor(componentId, initialTab, openerContext)" in controller_js
    assert "if (_componentEditor) return _componentEditor.openComponentDetailEditor(componentId, initialTab, openerContext);" in controller_js
    assert "loadCompositionTextPreviewForCurrentComposition" not in controller_js
    assert "window.addEventListener('message'" in host_js
    assert "if (target.hostTargetId) {" in host_js
    assert "await openRequestedTarget();" in host_js
    assert "setHostStatus(false, 'Saknar composition_id or component_id.')" not in host_js
    assert 'function renderComponentPalette() {' not in host_js
    assert 'BuilderComponentLibraryRuntime.create({' in host_js
    assert "const palette = document.getElementById('builderComponentPalette');" not in host_js
    assert "const builderPaletteSearch = document.getElementById(\"builderPaletteSearch\");" not in controller_js


def test_builder_editor_host_keeps_shared_component_library_runtime() -> None:
    host_js = Path("static/js/builder_editor_host.js").read_text(encoding="utf-8")

    assert "BuilderComponentLibraryRuntime.create({" in host_js
    assert "getComponentLibraryRuntime().renderPalette();" in host_js
    assert "const palette = document.getElementById('builderComponentPalette');" not in host_js
    assert "const searchInput = document.getElementById('builderPaletteSearch');" not in host_js
    assert "pill.addEventListener('click', async () => {" not in host_js
    assert "searchInputElement.addEventListener('input'" not in host_js
    assert "button.addEventListener('click', async () => {" not in host_js
    assert "builder-host-created-composition-ready" not in host_js
    assert "openCreateCompositionModal" not in host_js
    assert "BuilderDishCreateModal" not in host_js
    assert "data-rattbibliotek-picker" not in host_js
    assert "function renderPickerResults()" not in host_js
    assert "type: 'builder-host-close'" in host_js
    assert not list(Path("static/offshore2").glob("*component*.js"))
    runtime_js = Path("static/js/builder_component_library_runtime.js").read_text(encoding="utf-8")
    assert "'/api/builder/components'" in runtime_js
    assert "searchInputElement.addEventListener('input'" in runtime_js
    assert "button.addEventListener('click', async () => {" in runtime_js
    assert "No components match search" in runtime_js
    assert "No reusable components yet" in runtime_js


def test_builder_editor_host_only_resolves_existing_targets() -> None:
    host_js = Path("static/js/builder_editor_host.js").read_text(encoding="utf-8")
    assert "const hostKind = compositionId ? 'composition' : (componentId ? 'component' : '');" in host_js
    assert "url.searchParams.has('picker') || url.searchParams.has('create')" in host_js
    assert "This host opens existing Builder dishes or components only." in host_js
    assert "resolveCompositionEditTarget(sourceCompositionId)" in host_js
    assert "openComponentDetailEditor(component.component_id, 'overview')" in host_js
    assert "openPickerSurface" not in host_js
    assert "searchParams.get('picker')" not in host_js


def test_builder_composition_picker_is_a_separate_selector_host(client_admin) -> None:
    rv = client_admin.get("/builder-composition-picker?initial_name=Kottbullar", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'class="builder-workspace-v1 builder-composition-picker"' in html
    assert 'id="compositionPickerSearch"' in html
    assert 'data-composition-picker-results' in html
    assert 'data-composition-picker-create' in html
    assert 'data-composition-picker-close' in html
    assert 'Rättbibliotek' in html
    assert 'Skapa ny rätt' in html
    assert 'Sök rätt…' in html
    assert '<script src="/static/js/builder_composition_search.js"></script>' in html
    assert '<script src="/static/js/builder_dish_create.js"></script>' in html
    assert 'builder_editor_host.js' not in html
    assert 'resolveModal' not in html
    assert 'componentDetailEditorModal' not in html

    picker_js = Path("static/ui/builder_composition_picker.js").read_text(encoding="utf-8")
    assert "'/api/builder/compositions'" in picker_js
    assert "BuilderCompositionSearchRuntime.filterCompositionsBySearch" in picker_js
    assert "createEndpoint: '/api/builder/compositions/private'" in picker_js
    assert "BuilderDishCreateModal.open" in picker_js
    assert "sendToParent('menu-picker-selected', { composition_id: id });" in picker_js
    assert "composition: " not in picker_js
    assert "if (editAfterCreate && id)" in picker_js
    assert "window.location.replace('/builder-editor-host?composition_id='" in picker_js


def test_builder_composition_picker_respects_access_boundary(client_admin) -> None:
    rv = client_admin.get("/builder-composition-picker", headers=_headers(role="viewer"))

    assert rv.status_code == 403


def test_builder_workspace_uses_shared_composition_search_runtime() -> None:
    builder_js = Path("static/js/builder.js").read_text(encoding="utf-8")
    search_js = Path("static/js/builder_composition_search.js").read_text(encoding="utf-8")

    assert "BuilderCompositionSearchRuntime.filterCompositionsBySearch(" in builder_js
    assert "BuilderCompositionSearchRuntime.matchesCompositionSearch" not in builder_js
    assert "matchesCompositionSearch(composition, searchQuery)" in search_js
    assert "library_group" not in search_js

    host_js = Path("static/js/builder_editor_host.js").read_text(encoding="utf-8")
    assert "data-rattbibliotek-picker" not in host_js
    assert "function renderPickerResults()" not in host_js
