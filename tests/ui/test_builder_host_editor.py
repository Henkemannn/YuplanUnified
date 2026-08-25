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
    assert '<link rel="stylesheet" href="/static/css/builder.css?v=builder-modal-system-reset-1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_modal.css?v=builder-b1-modal-css-v1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_editor_host.css?v=builder-editor-host-v1">' in html
    assert '<script src="/static/js/builder_component_theme.js"></script>' in html
    assert '<script src="/static/js/builder_component_editor.js"></script>' in html
    assert '<script src="/static/js/builder_dish_editor.js"></script>' in html
    assert '<script src="/static/js/builder_modal_controller.js?v=builder-b1-modal-controller-v1"></script>' in html
    assert '<script src="/static/js/builder_editor_host.js?v=builder-editor-host-v1"></script>' in html
    assert html.find("builder_component_theme.js") < html.find("builder_editor_host.js?v=builder-editor-host-v1")
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' not in html
    assert 'builder-platform-header' not in html
    assert 'builder-shell' not in html
    assert 'builder-sidebar' not in html


def test_builder_editor_host_uses_same_assets_for_component_route(client_admin) -> None:
    rv = client_admin.get("/builder-editor-host?component_id=fish", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'class="builder-workspace-v1 builder-editor-host"' in html
    assert '<link rel="stylesheet" href="/static/css/builder.css?v=builder-modal-system-reset-1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_modal.css?v=builder-b1-modal-css-v1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_editor_host.css?v=builder-editor-host-v1">' in html
    assert '<script src="/static/js/builder_component_theme.js"></script>' in html
    assert '<script src="/static/js/builder_component_editor.js"></script>' in html
    assert '<script src="/static/js/builder_dish_editor.js"></script>' in html
    assert '<script src="/static/js/builder_editor_host.js?v=builder-editor-host-v1"></script>' in html
    assert html.find("builder_component_theme.js") < html.find("builder_editor_host.js?v=builder-editor-host-v1")
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' not in html


def test_builder_editor_host_without_target_still_loads_shell(client_admin) -> None:
    rv = client_admin.get("/builder-editor-host", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert '<style>' not in html
    assert 'class="builder-workspace-v1 builder-editor-host"' in html
    assert '<link rel="stylesheet" href="/static/css/builder.css?v=builder-modal-system-reset-1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_modal.css?v=builder-b1-modal-css-v1">' in html
    assert '<link rel="stylesheet" href="/static/css/builder_editor_host.css?v=builder-editor-host-v1">' in html
    assert '<script src="/static/js/builder_component_theme.js"></script>' in html
    assert '<script src="/static/js/builder_editor_host.js?v=builder-editor-host-v1"></script>' in html
    assert html.find("builder_component_theme.js") < html.find("builder_editor_host.js?v=builder-editor-host-v1")
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' not in html


def test_builder_editor_host_respects_access_boundary(client_admin) -> None:
    rv = client_admin.get(
        "/builder-editor-host?composition_id=plate_1",
        headers=_headers(role="viewer"),
    )

    assert rv.status_code == 403


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
    assert "prepareLinkedComponentForEdit" in controller_js
    assert "syncDishMenuNameVisibility" in controller_js
    assert "dishOverviewUseCustomMenuName" in controller_js
    assert "dishOverviewMenuName" in controller_js
    assert "_openLinkedComponentEditor" in controller_js
    assert "await _openLinkedComponentEditor(componentIdValue);" in controller_js
    assert "openComponentDetailEditor(componentId, initialTab)" in controller_js
    assert "if (_componentEditor) return _componentEditor.openComponentDetailEditor(componentId, initialTab);" in controller_js
    assert "loadCompositionTextPreviewForCurrentComposition" not in controller_js
    assert "window.addEventListener('message'" in host_js
    assert "if (target.hostTargetId) {" in host_js
    assert "await openRequestedTarget();" in host_js
    assert "setHostStatus(false, 'Saknar composition_id or component_id.')" not in host_js
