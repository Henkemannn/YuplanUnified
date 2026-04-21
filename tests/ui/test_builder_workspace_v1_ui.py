from __future__ import annotations


def test_builder_workspace_v1_route_renders_product_surface(client_admin) -> None:
    rv = client_admin.get("/builder-workspace-v1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Builder Workspace v1" in html
    assert 'id="libraryComponentsGrid" class="component-library-grid"' in html
    assert 'id="libraryCompositionsGrid" class="composition-library-grid"' in html
    assert 'id="resolveModal"' in html
    assert 'id="componentDetailModal"' in html
    assert 'id="btnCreateDish"' in html
    assert 'id="btnCreateComponent"' in html
    assert 'id="builderPaletteSearch"' in html
    assert 'id="builderComponentPalette" class="component-palette"' in html
    assert 'id="btnImportLibrary"' not in html
    assert 'id="importLibraryLines"' not in html
    assert 'id="btnImportFilePreview"' not in html
    assert 'id="btnImportFileConfirm"' not in html
    assert "Builder Internal UI" not in html
    assert "Importera ratter till biblioteket" not in html


def test_builder_internal_route_remains_internal_surface(client_admin) -> None:
    rv = client_admin.get("/builder", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Builder Internal UI" in html
    assert "Builder Workspace v1" not in html
    assert 'id="btnImportLibrary"' in html