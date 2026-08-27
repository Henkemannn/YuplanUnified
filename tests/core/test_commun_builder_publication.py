from __future__ import annotations

import json
import copy
from types import SimpleNamespace

from flask import current_app
from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentAliasRepository,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.menu_service import MenuServiceDB
from core.ui_blueprint import _apply_builder_reader_weekview_overview
from core.commun_builder_publication import CommunBuilderPublicationService
from core.commun_builder_projection import get_shadow_projection_reader


def _seed_site(app_session, site_id: str = "site-publication-1", tenant_id: int = 1) -> None:
    from core.db import get_new_session

    db = get_new_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :name, :tid, 0)"),
            {"id": site_id, "name": "Publication Site", "tid": tenant_id},
        )
        db.commit()
    finally:
        db.close()


def _seed_menu_and_link(site_id: str, year: int, week: int, builder_menu_id: str, builder_version: int) -> int:
    from core.db import get_session
    from core.menu_service import MenuServiceDB

    svc = MenuServiceDB()
    menu = svc.create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year)
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR REPLACE INTO commun_builder_menu_links "
                "(id, tenant_id, site_id, year, week, legacy_menu_id, builder_menu_id, builder_menu_version, source, projection_version, created_at, updated_at) "
                "VALUES(:id, :tenant_id, :site_id, :year, :week, :legacy_menu_id, :builder_menu_id, :builder_menu_version, :source, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": "link-publication-1",
                "tenant_id": 1,
                "site_id": site_id,
                "year": year,
                "week": week,
                "legacy_menu_id": menu.id,
                "builder_menu_id": builder_menu_id,
                "builder_menu_version": builder_version,
                "source": "pilot",
            },
        )
        db.commit()
    finally:
        db.close()
    return menu.id


def _mark_menu_published(menu_id: int) -> None:
    from core.db import get_new_session

    db = get_new_session()
    try:
        db.execute(text("UPDATE menus SET status='published' WHERE id=:id"), {"id": menu_id})
        db.commit()
    finally:
        db.close()


def _build_builder_menu_context_flow() -> tuple[BuilderMenuContextFlow, CompositionService]:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    builder_flow = BuilderFlow(
        component_service=ComponentService(repository=component_repository),
        composition_service=CompositionService(repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        component_alias_repository=InMemoryComponentAliasRepository(),
    )
    menu_context_flow = BuilderMenuContextFlow(
        menu_service=MenuService(composition_repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )
    return menu_context_flow, CompositionService(repository=composition_repository)


def _seed_publication_builder_context(
    *,
    site_id: str,
    year: int,
    week: int,
    builder_menu_id: str,
    builder_menu_version: int,
    composition_id: str,
    composition_name: str,
) -> tuple[BuilderMenuContextFlow, CompositionService]:
    builder_flow, composition_service = _build_builder_menu_context_flow()
    current_app.extensions["builder_menu_context_flow"] = builder_flow
    current_app.extensions["builder_flow"] = builder_flow
    builder_flow.create_menu(
        menu_id=builder_menu_id,
        site_id=site_id,
        week_key=f"{year}-W{week:02d}",
        version=builder_menu_version,
        status="published",
    )
    composition_service.create_composition(
        composition_id=composition_id,
        composition_name=composition_name,
    )
    builder_flow.add_composition_menu_row(
        menu_id=builder_menu_id,
        day="monday",
        meal_slot="lunch_alt1",
        composition_id=composition_id,
        sort_order=10,
    )
    return builder_flow, composition_service


def test_publish_mirrors_builder_publication_pin(app_session, monkeypatch):
    site_id = "site-publication-1"
    year = 2025
    week = 48
    _seed_site(app_session, site_id=site_id)
    menu_id = _seed_menu_and_link(site_id, year, week, "builder-menu-a", 1)

    from core.commun_builder_publication import CommunBuilderPublicationService

    monkeypatch.setattr(CommunBuilderPublicationService, "_verify_projection", lambda self, **kwargs: None)

    with app_session.app_context():
        _seed_publication_builder_context(
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-a",
            builder_menu_version=1,
            composition_id="comp_publication_a",
            composition_name="Publication Soup",
        )
        svc = MenuServiceDB()
        svc.publish_menu(tenant_id=1, menu_id=menu_id)

    from core.db import get_new_session

    db = get_new_session()
    try:
        pin = db.execute(
            text(
                "SELECT builder_menu_id, builder_menu_version, legacy_menu_id FROM commun_builder_publication_pins "
                "WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"
            ),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert pin is not None
        assert pin[0] == "builder-menu-a"
        assert int(pin[1]) == 1
        assert int(pin[2]) == int(menu_id)
    finally:
        db.close()


def test_publish_captures_immutable_snapshot_and_republish_refreshes_it(app_session, monkeypatch):
    site_id = "site-publication-immutable"
    year = 2025
    week = 52
    _seed_site(app_session, site_id=site_id)

    with app_session.app_context():
        builder_flow, composition_service = _build_builder_menu_context_flow()
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.extensions["builder_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-immutable", site_id=site_id, week_key="2025-W52", version=1, status="published")
        composition_service.create_composition(
            composition_id="comp_immutable",
            composition_name="Intern gryta",
            use_custom_menu_name=True,
            menu_name="Husets gryta",
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-immutable",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_immutable",
            sort_order=10,
        )
        legacy_menu_id = MenuServiceDB().create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year).id
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-immutable",
            source="manual",
        )

    monkeypatch.setattr(CommunBuilderPublicationService, "_verify_projection", lambda self, **kwargs: None)
    with app_session.app_context():
        MenuServiceDB().publish_menu(tenant_id=1, menu_id=legacy_menu_id)

        publication_service = CommunBuilderPublicationService()
        publication = publication_service.get_publication_for_week(tenant_id=1, site_id=site_id, year=year, week=week)
        assert publication is not None
        assert publication.projection_snapshot_json is not None
        assert "Husets gryta" in publication.projection_snapshot_json

        pinned_before = get_shadow_projection_reader().get_projection_for_pinned_menu(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-immutable",
            builder_menu_version=1,
        )
        assert pinned_before.status == "ok"
        assert pinned_before.projection is not None
        assert pinned_before.projection.rows[0].text == "Husets gryta"

        composition_service.update_composition_metadata(
            "comp_immutable",
            composition_name="Ny intern gryta",
            menu_name="Ny publik gryta",
        )

        pinned_after_edit = get_shadow_projection_reader().get_projection_for_pinned_menu(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-immutable",
            builder_menu_version=1,
        )
        assert pinned_after_edit.status == "ok"
        assert pinned_after_edit.projection is not None
        assert pinned_after_edit.projection.rows[0].text == "Husets gryta"

        MenuServiceDB().publish_menu(tenant_id=1, menu_id=legacy_menu_id)
        republished = get_shadow_projection_reader().get_projection_for_pinned_menu(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-immutable",
            builder_menu_version=1,
        )
        assert republished.status == "ok"
        assert republished.projection is not None
        assert republished.projection.rows[0].text == "Ny publik gryta"


def test_broken_publication_snapshot_fails_controlledly(app_session, monkeypatch):
    site_id = "site-publication-broken-snapshot"
    year = 2025
    week = 53
    _seed_site(app_session, site_id=site_id)

    with app_session.app_context():
        builder_flow, composition_service = _build_builder_menu_context_flow()
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.extensions["builder_flow"] = builder_flow
        builder_flow.create_menu(menu_id="builder-menu-broken", site_id=site_id, week_key="2025-W53", version=1, status="published")
        composition_service.create_composition(
            composition_id="comp_broken",
            composition_name="Stuvad potatis",
        )
        builder_flow.add_composition_menu_row(
            menu_id="builder-menu-broken",
            day="monday",
            meal_slot="lunch_alt1",
            composition_id="comp_broken",
            sort_order=10,
        )
        legacy_menu_id = MenuServiceDB().create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year).id
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-broken",
            source="manual",
        )

    monkeypatch.setattr(CommunBuilderPublicationService, "_verify_projection", lambda self, **kwargs: None)
    with app_session.app_context():
        MenuServiceDB().publish_menu(tenant_id=1, menu_id=legacy_menu_id)

    from core.db import get_session
    db = get_session()
    try:
        db.execute(
            text(
                "UPDATE commun_builder_publication_pins SET projection_snapshot_json=NULL WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"
            ),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        )
        db.commit()
    finally:
        db.close()

    broken = get_shadow_projection_reader().get_projection_for_pinned_menu(
        tenant_id=1,
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id="builder-menu-broken",
        builder_menu_version=1,
    )
    assert broken.status == "projection_error"
    assert broken.error == "publication_snapshot_missing"


def test_publish_legacy_published_menu_without_builder_link_keeps_legacy_published_without_pin(app_session, monkeypatch):
    site_id = "site-publication-legacy-only"
    year = 2025
    week = 47
    _seed_site(app_session, site_id=site_id)

    from core.menu_service import MenuServiceDB
    menu_id = MenuServiceDB().create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year).id
    _mark_menu_published(menu_id)

    monkeypatch.setattr(CommunBuilderPublicationService, "get_publication_for_week", lambda self, **kwargs: None)

    MenuServiceDB().publish_menu(tenant_id=1, menu_id=menu_id)

    from core.db import get_session

    db = get_session()
    try:
        menu_status = db.execute(text("SELECT status FROM menus WHERE id=:id"), {"id": menu_id}).fetchone()
        pin = db.execute(
            text("SELECT 1 FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert menu_status is not None and menu_status[0] == "published"
        assert pin is None
    finally:
        db.close()


def test_publish_legacy_published_menu_with_link_but_no_pin_creates_first_pin_and_is_idempotent(app_session, monkeypatch):
    site_id = "site-publication-first-pin"
    year = 2025
    week = 48
    _seed_site(app_session, site_id=site_id)
    menu_id = _seed_menu_and_link(site_id, year, week, "builder-menu-first", 1)
    _mark_menu_published(menu_id)

    monkeypatch.setattr(CommunBuilderPublicationService, "_verify_projection", lambda self, **kwargs: None)

    with app_session.app_context():
        _seed_publication_builder_context(
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-first",
            builder_menu_version=1,
            composition_id="comp_publication_first",
            composition_name="First Pin Soup",
        )
        svc = MenuServiceDB()
        svc.publish_menu(tenant_id=1, menu_id=menu_id)
        svc.publish_menu(tenant_id=1, menu_id=menu_id)

    from core.db import get_session

    db = get_session()
    try:
        menu_status = db.execute(text("SELECT status FROM menus WHERE id=:id"), {"id": menu_id}).fetchone()
        pin = db.execute(
            text(
                "SELECT builder_menu_id, builder_menu_version, legacy_menu_id FROM commun_builder_publication_pins "
                "WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"
            ),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert menu_status is not None and menu_status[0] == "published"
        assert pin is not None
        assert pin[0] == "builder-menu-first"
        assert int(pin[1]) == 1
        assert int(pin[2]) == int(menu_id)
    finally:
        db.close()


def test_publish_projection_failure_keeps_legacy_draft_and_no_pin(app_session, monkeypatch):
    site_id = "site-publication-2"
    year = 2025
    week = 49
    _seed_site(app_session, site_id=site_id)
    menu_id = _seed_menu_and_link(site_id, year, week, "builder-menu-b", 1)

    monkeypatch.setattr(
        "core.commun_builder_publication.CommunBuilderPublicationService._verify_projection",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("projection_verification_failed")),
    )

    svc = MenuServiceDB()
    try:
        svc.publish_menu(tenant_id=1, menu_id=menu_id)
    except RuntimeError:
        pass

    from core.db import get_session

    db = get_session()
    try:
        menu_status = db.execute(text("SELECT status FROM menus WHERE id=:id"), {"id": menu_id}).fetchone()
        pin = db.execute(
            text("SELECT 1 FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert menu_status is not None and menu_status[0] == "draft"
        assert pin is None
    finally:
        db.close()


def test_publish_pin_write_failure_keeps_legacy_draft(app_session, monkeypatch):
    site_id = "site-publication-3"
    year = 2025
    week = 50
    _seed_site(app_session, site_id=site_id)
    menu_id = _seed_menu_and_link(site_id, year, week, "builder-menu-c", 1)

    monkeypatch.setattr(
        "core.commun_builder_publication.CommunBuilderPublicationRepository.upsert_publication",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("pin_write_failed")),
    )

    svc = MenuServiceDB()
    try:
        svc.publish_menu(tenant_id=1, menu_id=menu_id)
    except RuntimeError:
        pass

    from core.db import get_session

    db = get_session()
    try:
        menu_status = db.execute(text("SELECT status FROM menus WHERE id=:id"), {"id": menu_id}).fetchone()
        pin = db.execute(
            text("SELECT 1 FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert menu_status is not None and menu_status[0] == "draft"
        assert pin is None
    finally:
        db.close()


def test_republish_failure_keeps_previous_pin(app_session, monkeypatch):
    site_id = "site-publication-4"
    year = 2025
    week = 51
    _seed_site(app_session, site_id=site_id)
    menu_id = _seed_menu_and_link(site_id, year, week, "builder-menu-d", 1)

    monkeypatch.setattr(CommunBuilderPublicationService, "_verify_projection", lambda self, **kwargs: None)

    with app_session.app_context():
        _seed_publication_builder_context(
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id="builder-menu-d",
            builder_menu_version=1,
            composition_id="comp_publication_d",
            composition_name="Republish Soup",
        )
        MenuServiceDB().publish_menu(tenant_id=1, menu_id=menu_id)

    from core.db import get_session

    db = get_session()
    try:
        pass
    finally:
        db.close()

    monkeypatch.setattr(
        "core.commun_builder_publication.CommunBuilderPublicationRepository.upsert_publication",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("republish_failed")),
    )

    with app_session.app_context():
        try:
            MenuServiceDB().publish_menu(tenant_id=1, menu_id=menu_id)
        except RuntimeError:
            pass

    db = get_session()
    try:
        pin = db.execute(
            text("SELECT builder_menu_version FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert pin is not None
        assert int(pin[0]) == 1
    finally:
        db.close()


def test_unpublish_legacy_published_menu_without_pin_keeps_builder_metadata_intact(app_session):
    site_id = "site-publication-unpublish"
    year = 2025
    week = 49
    _seed_site(app_session, site_id=site_id)
    menu_id = _seed_menu_and_link(site_id, year, week, "builder-menu-unpublish", 1)
    _mark_menu_published(menu_id)

    svc = MenuServiceDB()
    svc.unpublish_menu(tenant_id=1, menu_id=menu_id)

    from core.db import get_session

    db = get_session()
    try:
        menu_row = db.execute(
            text("SELECT status FROM menus WHERE id=:id"),
            {"id": menu_id},
        ).fetchone()
        link_row = db.execute(
            text("SELECT builder_menu_id FROM commun_builder_menu_links WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        pin_row = db.execute(
            text("SELECT 1 FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert menu_row is not None and menu_row[0] == "draft"
        assert link_row is not None and link_row[0] == "builder-menu-unpublish"
        assert pin_row is None
    finally:
        db.close()


def test_legacy_commit_failure_rolls_back_pin_and_status(app_session, monkeypatch):
    site_id = "site-publication-5"
    year = 2025
    week = 52
    _seed_site(app_session, site_id=site_id)
    menu_id = _seed_menu_and_link(site_id, year, week, "builder-menu-e", 1)

    monkeypatch.setattr(CommunBuilderPublicationService, "_verify_projection", lambda self, **kwargs: None)
    original_commit = Session.commit
    monkeypatch.setattr(Session, "commit", lambda self: (_ for _ in ()).throw(RuntimeError("commit_failed")))

    try:
        MenuServiceDB().publish_menu(tenant_id=1, menu_id=menu_id)
    except RuntimeError:
        pass

    from core.db import get_new_session

    db = get_new_session()
    try:
        menu_status = db.execute(text("SELECT status FROM menus WHERE id=:id"), {"id": menu_id}).fetchone()
        pin = db.execute(
            text("SELECT 1 FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": 1, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert menu_status is not None and menu_status[0] == "published"
        assert pin is None
    finally:
        db.close()

    monkeypatch.setattr(Session, "commit", original_commit)


def test_builder_reader_overview_override_updates_legacy_shape(app_session, monkeypatch):
    app = app_session
    monkeypatch.setattr(app, "feature_enabled", lambda name: name == "commun.builder.reader_v0", raising=False)

    vm = {
        "departments": [
            {
                "days": [
                    {
                        "day_of_week": 1,
                        "menu": {
                            "lunch_alt1": "Legacy lunch",
                            "lunch_alt2": None,
                            "lunch_dessert": None,
                            "dinner_alt1": None,
                            "dinner_alt2": None,
                        },
                        "has_menu_icon": True,
                    }
                ]
            }
        ]
    }

    monkeypatch.setattr(
        "core.commun_builder_publication.CommunBuilderPublicationService.get_publication_for_week",
        lambda self, **kwargs: SimpleNamespace(
            builder_menu_id="builder-menu-a",
            builder_menu_version=1,
            site_id=kwargs["site_id"],
            year=kwargs["year"],
            week=kwargs["week"],
        ),
    )
    monkeypatch.setattr(
        "core.commun_builder_projection.get_shadow_projection_reader",
        lambda: SimpleNamespace(
            get_projection_for_pinned_menu=lambda **kwargs: SimpleNamespace(
                status="ok",
                projection=SimpleNamespace(
                    rows=[
                        SimpleNamespace(day="mon", meal="lunch", variant_type="main", text="Builder lunch", resolved=True, error=None),
                        SimpleNamespace(day="mon", meal="dinner", variant_type="alt1", text="Builder dinner", resolved=True, error=None),
                    ]
                ),
            )
        ),
    )

    with app.app_context():
        changed = _apply_builder_reader_weekview_overview(vm, tenant_id=1, site_id="site-publication-1", year=2025, week=48)
    assert changed is True
    day = vm["departments"][0]["days"][0]
    assert day["menu"]["lunch_alt1"] == "Builder lunch"
    assert day["menu"]["dinner_alt1"] == "Builder dinner"
    assert day["has_menu_icon"] is True


def test_builder_reader_overview_override_falls_back_on_projection_error(app_session, monkeypatch):
    app = app_session
    monkeypatch.setattr(app, "feature_enabled", lambda name: name == "commun.builder.reader_v0", raising=False)

    vm = {
        "departments": [
            {
                "days": [
                    {
                        "day_of_week": 1,
                        "menu": {
                            "lunch_alt1": "Legacy lunch",
                            "lunch_alt2": None,
                            "lunch_dessert": None,
                            "dinner_alt1": None,
                            "dinner_alt2": None,
                        },
                        "has_menu_icon": True,
                    }
                ]
            }
        ]
    }
    before = copy.deepcopy(vm)

    monkeypatch.setattr(
        "core.commun_builder_publication.CommunBuilderPublicationService.get_publication_for_week",
        lambda self, **kwargs: SimpleNamespace(
            builder_menu_id="builder-menu-a",
            builder_menu_version=1,
            site_id=kwargs["site_id"],
            year=kwargs["year"],
            week=kwargs["week"],
        ),
    )
    monkeypatch.setattr(
        "core.commun_builder_projection.get_shadow_projection_reader",
        lambda: SimpleNamespace(
            get_projection_for_pinned_menu=lambda **kwargs: SimpleNamespace(
                status="projection_error",
                projection=None,
            )
        ),
    )

    with app.app_context():
        changed = _apply_builder_reader_weekview_overview(vm, tenant_id=1, site_id="site-publication-1", year=2025, week=48)
    assert changed is False
    assert vm == before
