from __future__ import annotations


def test_builder_workspace_v1_route_renders_product_surface(client_admin) -> None:
    rv = client_admin.get("/builder-workspace-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Builder Workspace v1" in html
    assert "Builder library" in html
    assert 'id="openNewDishModalBtn"' in html
    assert 'id="openComponentsModalBtn"' in html
    assert 'id="openImportModalBtn"' in html
    assert 'id="libraryComponentsGrid" class="component-library-grid"' in html
    assert 'id="libraryCompositionsGrid" class="composition-library-grid"' in html
    assert 'id="resolveModal"' in html
    assert 'id="componentDetailModal"' in html
    assert 'id="quickCreateModal"' in html
    assert 'id="componentsLibraryModal"' in html
    assert 'id="importLibraryModal"' in html
    assert 'href="/menu-builder-v1"' in html
    assert 'id="btnCreateDish"' in html
    assert 'id="btnCreateComponent"' in html
    assert 'id="btnImportLibrary"' in html
    assert 'id="importLibraryLines"' in html
    assert 'id="btnImportFilePreview"' in html
    assert 'id="btnImportFileConfirm"' in html
    assert 'id="importSummaryView"' in html
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