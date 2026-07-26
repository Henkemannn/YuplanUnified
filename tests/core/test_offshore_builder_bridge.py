from __future__ import annotations

from core.app_factory import create_app
from core.db import create_all
from core.offshore_builder_bridge import _service as builder_bridge_service
from core.planera_v2.contracts import PlanningComponentReference, PlanningCompositionReference


def _mk_app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with app.app_context():
        create_all()
    app.feature_registry.set("offshore.v2.enabled", True)
    return app


def test_bridge_builds_component_order_and_builder_deep_links() -> None:
    bridge = builder_bridge_service.build_composition_bridge(
        tenant_id=7,
        composition_reference=PlanningCompositionReference(
            composition_id="boeuf_bourguignon_potatismos",
            composition_name="Boeuf bourguignon med potatismos",
        ),
        component_references=(
            PlanningComponentReference(component_id="boeuf_bourguignon", component_name="Boeuf bourguignon", role="main", sort_order=1),
            PlanningComponentReference(component_id="potatismos", component_name="Potatismos", role="side", sort_order=2),
        ),
    )

    assert bridge is not None
    assert bridge["tenant_id"] == 7
    assert bridge["composition_id"] == "boeuf_bourguignon_potatismos"
    assert bridge["composition_name"] == "Boeuf bourguignon med potatismos"
    assert bridge["component_count"] == 2
    assert bridge["builder_url"] == "/builder?composition_id=boeuf_bourguignon_potatismos"
    assert bridge["render_url"] == "/builder?composition_id=boeuf_bourguignon_potatismos"
    assert bridge["readiness_url"] == "/builder?composition_id=boeuf_bourguignon_potatismos"

    components = bridge["components"]
    assert [item["component_name"] for item in components] == ["Boeuf bourguignon", "Potatismos"]
    assert [item["role"] for item in components] == ["main", "side"]
    assert [item["sort_order"] for item in components] == [1, 2]
    assert [item["details_url"] for item in components] == [
        "/builder?component_id=boeuf_bourguignon",
        "/builder?component_id=potatismos",
    ]


def test_bridge_filters_missing_data_and_keeps_empty_state_stable() -> None:
    assert builder_bridge_service.build_composition_bridge(tenant_id=1, composition_reference=None) is None

    empty_bridge = builder_bridge_service.build_composition_bridge(
        tenant_id=1,
        composition_reference=PlanningCompositionReference(composition_id="empty_comp", composition_name="Empty composition"),
        component_references=(),
    )
    assert empty_bridge is not None
    assert empty_bridge["component_count"] == 0
    assert empty_bridge["components"] == []

    filtered_bridge = builder_bridge_service.build_composition_bridge(
        tenant_id=1,
        composition_reference=PlanningCompositionReference(composition_id="missing_component_comp", composition_name="Missing component"),
        component_references=(
            PlanningComponentReference(component_id="", component_name="", role="main", sort_order=1),
            PlanningComponentReference(component_id="potatismos", component_name="Potatismos", role="side", sort_order=2),
        ),
    )
    assert filtered_bridge is not None
    assert filtered_bridge["component_count"] == 1
    assert [item["component_id"] for item in filtered_bridge["components"]] == ["potatismos"]


def test_builder_ui_deep_links_are_user_facing_and_role_protected() -> None:
    app = _mk_app()
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user_id"] = 42
        sess["role"] = "admin"
        sess["tenant_id"] = 1

    rv = client.get("/builder?composition_id=boeuf_bourguignon_potatismos")
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "<!doctype html>" in html
    assert 'script src="/static/js/builder.js"' in html
    assert 'id="componentDetailModal"' in html or 'id="componentDetailEditorModal"' in html
    assert 'id="resolveModal"' in html

    with client.session_transaction() as sess:
        sess["role"] = "viewer"

    forbidden = client.get("/builder?component_id=potatismos")
    assert forbidden.status_code == 403