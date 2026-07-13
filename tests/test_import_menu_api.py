import io
import json

from flask import Flask

from core.app_factory import create_app
from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.commun_builder_import import build_canonical_menu_id
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from core.menu import InMemoryCompositionAliasRepository, MenuService, create_composition_alias


def _app():
    return create_app({"TESTING": True})


def _login(client):
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 10
        sess["role"] = "admin"


def _set_site(client, site_id: str = "site_1"):
    with client.session_transaction() as sess:
        sess["site_id"] = site_id


def _build_flow():
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    component_service = ComponentService(repository=component_repository)
    composition_service = CompositionService(repository=composition_repository)
    menu_service = MenuService(composition_repository=composition_repository)

    builder_flow = BuilderFlow(
        component_service=component_service,
        composition_service=composition_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
    )
    return BuilderMenuContextFlow(
        menu_service=menu_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )


def test_menu_dry_run_true_sets_meta_flag(monkeypatch):
    app: Flask = _app()

    class DummyImporter:
        def parse(self, data, filename, mime):
            class Week:
                def __init__(self):
                    self.items = [
                        type(
                            "I",
                            (),
                            {
                                "day": "monday",
                                "meal": "lunch",
                                "variant_type": "alt1",
                                "dish_name": "Stew",
                            },
                        )()
                    ]

            return type("R", (), {"weeks": [Week()]})()

    import core.import_api as import_api_mod

    monkeypatch.setattr(import_api_mod, "_importer", DummyImporter())

    with app.test_client() as client:
        _login(client)
        _set_site(client)
        data = {"file": (io.BytesIO(b"x"), "menu.xlsx")}
        resp = client.post("/import/menu?dry_run=1", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["meta"]["dry_run"] is True
        assert body["meta"]["count"] == 1
        assert len(body["rows"]) == 1


def test_menu_unsupported_mime_415(monkeypatch):
    app: Flask = _app()
    import core.import_api as import_api_mod

    monkeypatch.setattr(import_api_mod, "_importer", None)
    with app.test_client() as client:
        _login(client)
        _set_site(client)
        data = {"file": (io.BytesIO(b"x"), "menu.xlsx")}
        resp = client.post("/import/menu", data=data, content_type="multipart/form-data")
        assert resp.status_code in (415, 400)  # 415 when importer missing


def test_menu_canonical_import_persists_builder_menu_and_reuses_id(monkeypatch, client_admin):
    app: Flask = client_admin.application
    flow = _build_flow()

    class DummyImporter:
        def parse(self, data, filename, mime):
            from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport

            items = [
                ImportedMenuItem(
                    day="monday",
                    meal="lunch",
                    variant_type="alt1",
                    dish_name="Stew",
                )
            ]
            return MenuImportResult(weeks=[WeekImport(year=2026, week=16, items=items)])

    import core.import_api as import_api_mod

    monkeypatch.setattr(import_api_mod, "_importer", DummyImporter())
    monkeypatch.setattr(
        CommunBuilderMenuLinkService,
        "_validate_site_tenant_access",
        lambda self, tenant_id, site_id: None,
    )

    with app.app_context():
        app.extensions["builder_menu_context_flow"] = flow
        flow._library_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
        create_composition_alias(
            alias_repository=flow._library_flow._alias_repository,
            alias_id="a1",
            composition_id="plate_1",
            alias_text="Fish Plate",
            composition_repository=flow._composition_repository,
        )

        _login(client_admin)
        _set_site(client_admin)
        app.feature_registry.set("commun.builder.canonical_import_v0", True)

        resp1 = client_admin.post(
            "/import/menu",
            data={"file": (io.BytesIO(b"x"), "menu.xlsx")},
            content_type="multipart/form-data",
        )
        assert resp1.status_code == 200
        body1 = json.loads(resp1.data)
        assert "canonical_import" in body1
        canonical1 = body1["canonical_import"][0]
        assert canonical1["status"] == "created"
        assert canonical1["imported_count"] == 1
        assert canonical1["menu_id"].startswith("builder-menu-")

        resp2 = client_admin.post(
            "/import/menu",
            data={"file": (io.BytesIO(b"x"), "menu.xlsx")},
            content_type="multipart/form-data",
        )
        assert resp2.status_code == 200
        body2 = json.loads(resp2.data)
        assert body2["canonical_import"][0]["status"] == "unchanged"
        assert body2["canonical_import"][0]["menu_id"] == canonical1["menu_id"]

        rows = flow.list_menu_rows(canonical1["menu_id"])
        assert len(rows) == 1
        assert rows[0]["meal_slot"] == "lunch_alt1"

        app.feature_registry.set("commun.builder.canonical_import_v0", False)


def test_menu_canonical_import_failure_returns_500_and_restores_state(monkeypatch, client_admin):
    app: Flask = client_admin.application
    flow = _build_flow()

    class DummyImporter:
        def parse(self, data, filename, mime):
            from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport

            items = [
                ImportedMenuItem(
                    day="monday",
                    meal="lunch",
                    variant_type="alt1",
                    dish_name="Fish Plate",
                )
            ]
            return MenuImportResult(weeks=[WeekImport(year=2026, week=20, items=items)])

    import core.import_api as import_api_mod

    monkeypatch.setattr(import_api_mod, "_importer", DummyImporter())
    monkeypatch.setattr(
        CommunBuilderMenuLinkService,
        "_validate_site_tenant_access",
        lambda self, tenant_id, site_id: None,
    )
    monkeypatch.setattr(
        CommunBuilderMenuLinkService,
        "create_or_replace_link",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("linkage failed")),
    )

    with app.app_context():
        app.extensions["builder_menu_context_flow"] = flow
        flow._library_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
        create_composition_alias(
            alias_repository=flow._library_flow._alias_repository,
            alias_id="a1",
            composition_id="plate_1",
            alias_text="Fish Plate",
            composition_repository=flow._composition_repository,
        )

        _login(client_admin)
        _set_site(client_admin)
        app.feature_registry.set("commun.builder.canonical_import_v0", True)

        resp = client_admin.post(
            "/import/menu",
            data={"file": (io.BytesIO(b"x"), "menu.xlsx")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 500
        body = json.loads(resp.data)
        assert body["ok"] is False
        assert body["error"] == "canonical_import_failed"
        assert body["canonical_import"]["status"] == "failed"
        menu_id = build_canonical_menu_id(tenant_id=1, site_id="site_1", year=2026, week=20, import_type="menu")
        assert flow._menu_service.get_menu(menu_id) is None

        app.feature_registry.set("commun.builder.canonical_import_v0", False)
