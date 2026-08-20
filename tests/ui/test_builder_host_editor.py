from __future__ import annotations


def _headers(*, role: str = "admin", tenant_id: int = 1, user_id: int = 11) -> dict[str, str]:
    return {
        "X-User-Role": role,
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": str(user_id),
    }


def test_builder_host_entry_reuses_canonical_dish_editor(client_admin) -> None:
    rv = client_admin.get("/builder-workspace-v1?composition_id=plate_1", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'class="builder-workspace-v1 builder-host-entry"' in html
    assert 'body.builder-host-entry .builder-platform-layout' in html
    assert '<script src="/static/js/builder_component_editor.js"></script>' in html
    assert '<script src="/static/js/builder_dish_editor.js"></script>' in html
    assert '<script src="/static/js/builder_modal_controller.js?v=builder-b1-modal-controller-v1"></script>' in html
    assert '<script src="/static/js/builder.js?v=builder-modal-system-reset-1"></script>' in html
    assert html.count('builder_component_editor.js') == 1
    assert html.count('builder_dish_editor.js') == 1
    assert 'builder_light' not in html

    js = client_admin.get("/static/js/builder.js").data.decode("utf-8")
    assert 'openCompositionFromLibrary(_builderHostLocation.compositionId);' in js
    assert 'builder-host-close' in js


def test_builder_host_entry_reuses_canonical_component_editor(client_admin) -> None:
    rv = client_admin.get("/builder-workspace-v1?component_id=fish", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'class="builder-workspace-v1 builder-host-entry"' in html
    assert '<script src="/static/js/builder_component_editor.js"></script>' in html
    assert '<script src="/static/js/builder_dish_editor.js"></script>' in html
    assert 'builder_light' not in html

    js = client_admin.get("/static/js/builder.js").data.decode("utf-8")
    assert 'openComponentDetailEditor(_builderHostLocation.componentId);' in js
    assert 'String(detail.kind || "") !== _builderHostLocation.hostKind' in js
    assert 'builder-host-close' in js


def test_builder_host_close_semantics_are_root_only(client_admin) -> None:
    js = client_admin.get("/static/js/builder_modal_controller.js").data.decode("utf-8")

    assert '_builderHostLocation' not in js
    assert '_notifyHostClose({ kind: "component", component_id: activeComponentId });' in js
    assert '_notifyHostClose({ kind: "composition", composition_id: activeCompositionId });' in js


def test_builder_host_entry_respects_existing_access_boundary(client_admin) -> None:
    rv = client_admin.get(
        "/builder-workspace-v1?composition_id=plate_1",
        headers=_headers(role="viewer"),
    )

    assert rv.status_code == 403


def test_builder_workspace_normal_route_still_renders_workspace_shell(client_admin) -> None:
    rv = client_admin.get("/builder-workspace-v1", headers=_headers())

    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'class="builder-workspace-v1 builder-host-entry"' not in html
    assert 'Builder Workspace v1' in html
    assert 'builder-platform-header' in html
    assert 'builder-shell' in html
    assert 'builder_light' not in html
