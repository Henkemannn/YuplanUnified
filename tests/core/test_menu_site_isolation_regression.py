from __future__ import annotations

import pytest
from sqlalchemy import text

from core.db import get_new_session
from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport
from core.menu_import_service import MenuImportService
from core.menu_service import MenuServiceDB


TENANT_A = 4101
TENANT_B = 4102
TENANT_C = 4103
SITE_A1 = "04g-site-a1"
SITE_A2 = "04g-site-a2"
SITE_B1 = "04g-site-b1"
SITE_C1 = "04g-site-c1"
SITE_C2 = "04g-site-c2"


def _seed_sites() -> None:
    db = get_new_session()
    try:
        db.execute(
            text(
                "INSERT OR IGNORE INTO tenants(id, name, active) "
                "VALUES (:tenant_id, :name, 1)"
            ),
            {"tenant_id": TENANT_A, "name": "04G Tenant A"},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO tenants(id, name, active) "
                "VALUES (:tenant_id, :name, 1)"
            ),
            {"tenant_id": TENANT_B, "name": "04G Tenant B"},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO tenants(id, name, active) "
                "VALUES (:tenant_id, :name, 1)"
            ),
            {"tenant_id": TENANT_C, "name": "04G Tenant C"},
        )
        for site_id, tenant_id in (
            (SITE_A1, TENANT_A),
            (SITE_A2, TENANT_A),
            (SITE_B1, TENANT_B),
            (SITE_C1, TENANT_C),
            (SITE_C2, TENANT_C),
        ):
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
                    "VALUES (:site_id, :name, :tenant_id, 0)"
                ),
                {
                    "site_id": site_id,
                    "name": site_id,
                    "tenant_id": tenant_id,
                },
            )
        db.commit()
    finally:
        db.close()


def _menu_row(menu_id: int) -> tuple:
    db = get_new_session()
    try:
        return tuple(
            db.execute(
                text(
                    "SELECT id, tenant_id, site_id, week, year, status "
                    "FROM menus WHERE id=:menu_id"
                ),
                {"menu_id": menu_id},
            ).one()
        )
    finally:
        db.close()


def test_site_menus_are_independent_and_publication_references_stay_bound(app_session):
    with app_session.app_context():
        _seed_sites()
        service = MenuServiceDB()
        menu_a = service.create_or_get_menu(TENANT_A, SITE_A1, 11, 2031)

        db = get_new_session()
        try:
            db.execute(
                text("UPDATE menus SET status='published' WHERE id=:menu_id"),
                {"menu_id": menu_a.id},
            )
            db.execute(
                text(
                    "INSERT INTO dishes(id, tenant_id, site_id, name, category) "
                    "VALUES (94101, :tenant_id, :site_id, 'Site A dish', 'main')"
                ),
                {"tenant_id": TENANT_A, "site_id": SITE_A1},
            )
            db.execute(
                text(
                    "INSERT INTO menu_variants(menu_id, day, meal, variant_type, dish_id) "
                    "VALUES (:menu_id, 'mon', 'lunch', 'alt1', 94101)"
                ),
                {"menu_id": menu_a.id},
            )
            db.execute(
                text(
                    "INSERT INTO commun_builder_menu_links("
                    "id, tenant_id, site_id, year, week, legacy_menu_id, "
                    "builder_menu_id, builder_menu_version, source, projection_version, "
                    "created_at, updated_at) VALUES("
                    "'04g-link-a', :tenant_id, :site_id, 2031, 11, :menu_id, "
                    "'04g-builder-a', 1, 'manual', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "tenant_id": TENANT_A,
                    "site_id": SITE_A1,
                    "menu_id": menu_a.id,
                },
            )
            db.execute(
                text(
                    "INSERT INTO commun_builder_publication_pins("
                    "id, tenant_id, site_id, year, week, legacy_menu_id, "
                    "builder_menu_id, builder_menu_version, source, projection_snapshot_json, "
                    "created_at, updated_at) VALUES("
                    "'04g-pin-a', :tenant_id, :site_id, 2031, 11, :menu_id, "
                    "'04g-builder-a', 1, 'manual', 'site-a-snapshot', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "tenant_id": TENANT_A,
                    "site_id": SITE_A1,
                    "menu_id": menu_a.id,
                },
            )
            db.commit()
        finally:
            db.close()

        menu_b = service.create_or_get_menu(TENANT_A, SITE_A2, 11, 2031)

        assert menu_b.id != menu_a.id
        assert _menu_row(menu_a.id) == (
            menu_a.id,
            TENANT_A,
            SITE_A1,
            11,
            2031,
            "published",
        )
        assert _menu_row(menu_b.id) == (
            menu_b.id,
            TENANT_A,
            SITE_A2,
            11,
            2031,
            "draft",
        )

        db = get_new_session()
        try:
            assert db.execute(
                text("SELECT COUNT(*) FROM menu_variants WHERE menu_id=:menu_id"),
                {"menu_id": menu_b.id},
            ).scalar_one() == 0
            assert tuple(
                db.execute(
                    text(
                        "SELECT site_id, legacy_menu_id "
                        "FROM commun_builder_menu_links WHERE id='04g-link-a'"
                    )
                ).one()
            ) == (SITE_A1, menu_a.id)
            assert tuple(
                db.execute(
                    text(
                        "SELECT site_id, legacy_menu_id "
                        "FROM commun_builder_publication_pins WHERE id='04g-pin-a'"
                    )
                ).one()
            ) == (SITE_A1, menu_a.id)
        finally:
            db.close()


def test_tenants_cannot_reuse_each_others_menus(app_session):
    with app_session.app_context():
        _seed_sites()
        service = MenuServiceDB()
        menu_a = service.create_or_get_menu(TENANT_A, SITE_A1, 12, 2031)
        menu_b = service.create_or_get_menu(TENANT_B, SITE_B1, 12, 2031)

        assert menu_a.id != menu_b.id
        assert menu_a.site_id == SITE_A1
        assert menu_b.site_id == SITE_B1
        assert menu_a.tenant_id == TENANT_A
        assert menu_b.tenant_id == TENANT_B


def test_tenant_site_mismatch_is_rejected(app_session):
    with app_session.app_context():
        _seed_sites()
        with pytest.raises(ValueError, match="site_tenant_mismatch"):
            MenuServiceDB().create_or_get_menu(TENANT_B, SITE_A1, 13, 2031)


def test_variant_rejects_cross_site_and_unclassified_dishes_without_writes(
    app_session,
):
    with app_session.app_context():
        _seed_sites()
        db = get_new_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dishes(id, tenant_id, site_id, name, category) "
                    "VALUES (94111, :tenant_id, :other_site_id, 'Other site', 'main'), "
                    "(94112, :tenant_id, NULL, 'Unclassified', 'main')"
                ),
                {"tenant_id": TENANT_A, "other_site_id": SITE_A2},
            )
            db.commit()
        finally:
            db.close()

        service = MenuServiceDB()
        for dish_id, error in (
            (94111, "dish_site_mismatch"),
            (94112, "dish_site_mismatch"),
        ):
            with pytest.raises(ValueError, match=error):
                service.set_variant_atomic(
                    tenant_id=TENANT_A,
                    site_id=SITE_A1,
                    week=15,
                    year=2031,
                    day="mon",
                    meal="lunch",
                    variant_type="main",
                    dish_id=dish_id,
                )

        db = get_new_session()
        try:
            assert db.execute(
                text(
                    "SELECT COUNT(*) FROM menus "
                    "WHERE tenant_id=:tenant_id AND site_id=:site_id "
                    "AND week=15 AND year=2031"
                ),
                {"tenant_id": TENANT_A, "site_id": SITE_A1},
            ).scalar_one() == 0
        finally:
            db.close()


def test_null_site_menu_is_not_implicitly_bound(app_session):
    with app_session.app_context():
        _seed_sites()
        db = get_new_session()
        try:
            menu_id = db.execute(
                text(
                    "INSERT INTO menus(tenant_id, site_id, week, year, status) "
                    "VALUES (:tenant_id, NULL, 14, 2031, 'published') "
                    "RETURNING id"
                ),
                {"tenant_id": TENANT_A},
            ).scalar_one()
            db.commit()
        finally:
            db.close()

        rebound = MenuServiceDB().create_or_get_menu(TENANT_A, SITE_A2, 14, 2031)

        assert _menu_row(menu_id) == (
            menu_id,
            TENANT_A,
            None,
            14,
            2031,
            "published",
        )
        assert rebound.id != menu_id
        assert rebound.site_id == SITE_A2


def test_legacy_tenant_week_uniqueness_returns_conflict_without_move(app_session):
    with app_session.app_context():
        _seed_sites()
        db = get_new_session()
        try:
            db.execute(
                text(
                    "CREATE UNIQUE INDEX uq_04g_legacy_menu_tenant_week "
                    "ON menus(tenant_id, week, year) WHERE tenant_id = 4103"
                )
            )
            db.commit()
        finally:
            db.close()

        try:
            service = MenuServiceDB()
            menu_a = service.create_or_get_menu(TENANT_C, SITE_C1, 16, 2031)
            with pytest.raises(ValueError, match="menu_site_conflict"):
                service.create_or_get_menu(TENANT_C, SITE_C2, 16, 2031)
            assert _menu_row(menu_a.id)[2:] == (
                SITE_C1,
                16,
                2031,
                "draft",
            )
        finally:
            db = get_new_session()
            try:
                db.execute(text("DROP INDEX uq_04g_legacy_menu_tenant_week"))
                db.commit()
            finally:
                db.close()


def test_integrity_error_recovery_never_reuses_another_site(
    app_session, monkeypatch
):
    with app_session.app_context():
        _seed_sites()
        db = get_new_session()
        try:
            db.execute(
                text(
                    "CREATE UNIQUE INDEX uq_04g_integrity_menu_tenant_week "
                    "ON menus(tenant_id, week, year) WHERE tenant_id = 4103"
                )
            )
            db.commit()
        finally:
            db.close()

        try:
            service = MenuServiceDB()
            monkeypatch.setattr(
                service, "_has_legacy_menu_uniqueness", lambda db: False
            )
            menu_a = service.create_or_get_menu(TENANT_C, SITE_C1, 17, 2031)
            with pytest.raises(ValueError, match="menu_site_conflict"):
                service.create_or_get_menu(TENANT_C, SITE_C2, 17, 2031)
            assert _menu_row(menu_a.id)[2:] == (
                SITE_C1,
                17,
                2031,
                "draft",
            )
        finally:
            db = get_new_session()
            try:
                db.execute(text("DROP INDEX uq_04g_integrity_menu_tenant_week"))
                db.commit()
            finally:
                db.close()


def test_menu_import_reuses_only_the_current_sites_dish(app_session, monkeypatch):
    with app_session.app_context():
        _seed_sites()
        db = get_new_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dishes(id, tenant_id, site_id, name, category) "
                    "VALUES (94201, :tenant_id, :site_id, 'Same Name', 'main'), "
                    "(94202, :tenant_id, :other_site_id, 'Same Name', 'main')"
                ),
                {
                    "tenant_id": TENANT_A,
                    "site_id": SITE_A1,
                    "other_site_id": SITE_A2,
                },
            )
            db.commit()
        finally:
            db.close()

        monkeypatch.setattr(
            "core.menu_import_service.import_menu_result_to_builder_canonical",
            lambda *args, **kwargs: [],
        )
        monkeypatch.setattr(MenuImportService, "_verify_builder_linkage", lambda *args, **kwargs: None)
        result = MenuImportResult(
            weeks=[
                WeekImport(
                    year=2031,
                    week=18,
                    items=[
                        ImportedMenuItem(
                            day="monday",
                            meal="lunch",
                            variant_type="main",
                            dish_name="Same Name",
                        )
                    ],
                )
            ]
        )

        MenuImportService(MenuServiceDB()).apply(TENANT_A, SITE_A2, result)

        db = get_new_session()
        try:
            assert db.execute(
                text(
                    "SELECT mv.dish_id FROM menu_variants mv "
                    "JOIN menus m ON m.id=mv.menu_id "
                    "WHERE m.tenant_id=:tenant_id AND m.site_id=:site_id"
                ),
                {"tenant_id": TENANT_A, "site_id": SITE_A2},
            ).scalar_one() == 94202
        finally:
            db.close()


def test_menu_import_rolls_back_menu_dishes_and_variants_on_failure(
    app_session, monkeypatch
):
    with app_session.app_context():
        _seed_sites()
        result = MenuImportResult(
            weeks=[
                WeekImport(
                    year=2031,
                    week=19,
                    items=[
                        ImportedMenuItem(
                            day="monday",
                            meal="lunch",
                            variant_type="main",
                            dish_name="Rollback first",
                        ),
                        ImportedMenuItem(
                            day="tuesday",
                            meal="lunch",
                            variant_type="main",
                            dish_name="Rollback second",
                        ),
                    ],
                )
            ]
        )
        monkeypatch.setattr(
            "core.menu_import_service.import_menu_result_to_builder_canonical",
            lambda *args, **kwargs: [],
        )
        monkeypatch.setattr(MenuImportService, "_verify_builder_linkage", lambda *args, **kwargs: None)
        original = MenuServiceDB._set_variant_in_session
        calls = {"count": 0}

        def fail_after_first(self, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("forced import failure")
            return original(self, **kwargs)

        monkeypatch.setattr(MenuServiceDB, "_set_variant_in_session", fail_after_first)

        with pytest.raises(RuntimeError, match="forced import failure"):
            MenuImportService(MenuServiceDB()).apply(TENANT_A, SITE_A1, result)

        db = get_new_session()
        try:
            assert db.execute(
                text(
                    "SELECT COUNT(*) FROM menus "
                    "WHERE tenant_id=:tenant_id AND site_id=:site_id "
                    "AND week=19 AND year=2031"
                ),
                {"tenant_id": TENANT_A, "site_id": SITE_A1},
            ).scalar_one() == 0
            assert db.execute(
                text(
                    "SELECT COUNT(*) FROM dishes WHERE tenant_id=:tenant_id "
                    "AND site_id=:site_id AND name LIKE 'Rollback %'"
                ),
                {"tenant_id": TENANT_A, "site_id": SITE_A1},
            ).scalar_one() == 0
            assert db.execute(
                text(
                    "SELECT COUNT(*) FROM menu_variants mv "
                    "JOIN menus m ON m.id=mv.menu_id "
                    "WHERE m.tenant_id=:tenant_id AND m.site_id=:site_id "
                    "AND m.week=19 AND m.year=2031"
                ),
                {"tenant_id": TENANT_A, "site_id": SITE_A1},
            ).scalar_one() == 0
        finally:
            db.close()
