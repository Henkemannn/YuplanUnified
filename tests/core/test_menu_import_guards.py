from __future__ import annotations

import pytest
from sqlalchemy import text

from core.commun_builder_import import CommunBuilderCanonicalImportError
from core.commun_builder_publication import CommunBuilderPublicationService
from core.db import get_new_session
from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport
from core.menu_import_service import MenuImportOperationError, MenuImportService
from core.menu_service import MenuServiceDB
from core.models import MenuImportGuard


SITE_ID = "guard-site"


def _seed_site() -> None:
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR IGNORE INTO sites(id, name, tenant_id) VALUES "
                "(:id, 'Guard Site', 1)"
            ),
            {"id": SITE_ID},
        )
        db.commit()
    finally:
        db.close()


def _result(week: int = 20) -> MenuImportResult:
    return MenuImportResult(
        weeks=[
            WeekImport(
                year=2035,
                week=week,
                items=[
                    ImportedMenuItem(
                        day="monday",
                        meal="lunch",
                        variant_type="main",
                        dish_name="Guard Dish",
                    )
                ],
            )
        ]
    )


def test_successful_import_completes_guard(app_session, monkeypatch):
    with app_session.app_context():
        _seed_site()
        monkeypatch.setattr(
            "core.menu_import_service.import_menu_result_to_builder_canonical",
            lambda *args, **kwargs: [],
        )
        monkeypatch.setattr(
            MenuImportService,
            "_verify_builder_linkage",
            lambda *args, **kwargs: None,
        )

        MenuImportService(MenuServiceDB()).apply(1, SITE_ID, _result())

        db = get_new_session()
        try:
            guards = (
                db.query(MenuImportGuard)
                .filter_by(tenant_id=1, site_id=SITE_ID, year=2035, week=20)
                .order_by(MenuImportGuard.id.desc())
                .all()
            )
            assert guards
            guard = guards[0]
            assert guard.status == "completed"
            assert guard.active_key is None
            assert guard.operation_id
        finally:
            db.close()


def test_needs_review_blocks_new_import_after_builder_failure(app_session, monkeypatch):
    with app_session.app_context():
        _seed_site()

        def fail(*args, **kwargs):
            raise CommunBuilderCanonicalImportError(
                "builder failed",
                recovery_state={
                    "restored": False,
                    "manual_review_required": True,
                },
            )

        monkeypatch.setattr(
            "core.menu_import_service.import_menu_result_to_builder_canonical",
            fail,
        )

        with pytest.raises(MenuImportOperationError) as error:
            MenuImportService(MenuServiceDB()).apply(1, SITE_ID, _result(21))
        assert error.value.status == "needs_review"
        assert error.value.operation_id

        db = get_new_session()
        try:
            guard = (
                db.query(MenuImportGuard)
                .filter_by(year=2035, week=21)
                .one()
            )
            assert guard.status == "needs_review"
            operation_id = guard.operation_id
        finally:
            db.close()

        monkeypatch.setattr(
            "core.menu_import_service.import_menu_result_to_builder_canonical",
            lambda *args, **kwargs: [],
        )
        with pytest.raises(ValueError, match="menu_import_in_progress"):
            MenuImportService(MenuServiceDB()).apply(1, SITE_ID, _result(21))

        db = get_new_session()
        try:
            assert db.query(MenuImportGuard).filter_by(operation_id=operation_id).one().status == "needs_review"
        finally:
            db.close()


def test_incomplete_import_blocks_publication(app_session):
    with app_session.app_context():
        _seed_site()
        db = get_new_session()
        try:
            db.add(
                MenuImportGuard(
                    operation_id="manual-review-operation",
                    tenant_id=1,
                    site_id=SITE_ID,
                    year=2035,
                    week=22,
                    status="needs_review",
                    active_key=f"1:{SITE_ID}:2035:22",
                )
            )
            db.commit()
        finally:
            db.close()

        with pytest.raises(RuntimeError, match="menu_import_not_ready:needs_review"):
            CommunBuilderPublicationService().publish_week(
                tenant_id=1,
                site_id=SITE_ID,
                year=2035,
                week=22,
                legacy_menu_id=None,
            )
