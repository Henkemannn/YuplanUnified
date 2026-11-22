from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError

from .commun_builder_import import import_menu_result_to_builder_canonical
from .db import get_new_session
from .importers.base import ImportedMenuItem, MenuImportResult
from .menu_service import MenuServiceDB
from .models import Dish, MenuImportGuard


class MenuImportOperationError(RuntimeError):
    def __init__(self, message: str, *, operation_id: str, status: str) -> None:
        super().__init__(message)
        self.operation_id = operation_id
        self.status = status


class MenuImportService:
    """Coordinates parsed import data with persistence layer.
    Responsibilities:
    - Ensure Menu exists for week/year
    - Upsert Dishes (by name + tenant scope)
    - Set variants
    Returns stats per week.
    """

    def __init__(self, menu_service: MenuServiceDB):
        self.menu_service = menu_service

    def apply(self, tenant_id: int, site_id: str, result: MenuImportResult) -> dict:
        if not any(week_block.items for week_block in result.weeks):
            raise ValueError("No menu items recognized; no menus were created.")

        summary = []
        legacy_menu_ids_by_week: dict[tuple[int, int], int] = {}
        weeks = sorted(
            {
                (int(week_block.year), int(week_block.week))
                for week_block in result.weeks
                if week_block.items
            }
        )
        operation_id = str(uuid.uuid4())
        # This transaction is owned exclusively by the legacy import. Builder
        # linkage uses its own session and runs only after this session commits.
        db = get_new_session()
        guards_created = False
        try:
            effective_tenant_id = self.menu_service._verified_site_tenant_id(db, site_id)
            if effective_tenant_id is None:
                raise ValueError("site_tenant_required")
            self._create_guards(
                db,
                operation_id=operation_id,
                tenant_id=int(effective_tenant_id),
                site_id=str(site_id),
                weeks=weeks,
            )
            guards_created = True
            for week_block in result.weeks:
                if not week_block.items:
                    continue
                created = 0
                updated = 0
                skipped = 0
                menu = self.menu_service._create_or_get_menu_in_session(
                    db,
                    effective_tenant_id,
                    site_id,
                    week_block.week,
                    week_block.year,
                )
                legacy_menu_ids_by_week[(int(week_block.year), int(week_block.week))] = int(menu.id)
                # Preload existing variants map
                existing_map = self._existing_variant_map(db, menu.id)
                for item in week_block.items:
                    dish_id = self._get_or_create_dish(
                        db, effective_tenant_id, site_id, item
                    )
                    key = (item.day, item.meal, item.variant_type)
                    prev = existing_map.get(key)
                    if prev == dish_id:
                        skipped += 1
                        continue
                    if prev is None:
                        created += 1
                    else:
                        updated += 1
                    self.menu_service._set_variant_in_session(
                        db=db,
                        tenant_id=effective_tenant_id,
                        site_id=site_id,
                        menu=menu,
                        day=item.day,
                        meal=item.meal,
                        variant_type=item.variant_type,
                        dish_id=dish_id,
                    )
                summary.append(
                    {
                        "week": week_block.week,
                        "year": week_block.year,
                        "created": created,
                        "updated": updated,
                        "skipped": skipped,
                        "total": len(week_block.items),
                    }
                )

            db.commit()

            if weeks:
                outcomes = import_menu_result_to_builder_canonical(
                    result,
                    tenant_id=int(effective_tenant_id),
                    site_id=str(site_id),
                    import_type="menu",
                    legacy_menu_ids_by_week=legacy_menu_ids_by_week,
                    restore_on_error=False,
                )
                self._verify_builder_linkage(
                    outcomes,
                    effective_tenant_id=int(effective_tenant_id),
                    site_id=str(site_id),
                    legacy_menu_ids_by_week=legacy_menu_ids_by_week,
                )
            self._complete_guards(db, operation_id)
            return {"weeks": summary, "warnings": result.warnings, "errors": result.errors}
        except Exception as exc:
            db.rollback()
            if guards_created:
                self._mark_guards_needs_review(
                    operation_id,
                    error_code=type(exc).__name__,
                )
                raise MenuImportOperationError(
                    f"menu import needs review (operation_id={operation_id}): {exc}",
                    operation_id=operation_id,
                    status="needs_review",
                ) from exc
            raise
        finally:
            db.close()

    def _create_guards(
        self,
        db,
        *,
        operation_id: str,
        tenant_id: int,
        site_id: str,
        weeks: list[tuple[int, int]],
    ) -> None:
        for year, week in weeks:
            db.add(
                MenuImportGuard(
                    operation_id=operation_id,
                    tenant_id=tenant_id,
                    site_id=site_id,
                    year=year,
                    week=week,
                    status="in_progress",
                    active_key=f"{tenant_id}:{site_id}:{year}:{week}",
                )
            )
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("menu_import_in_progress") from exc

    @staticmethod
    def _complete_guards(db, operation_id: str) -> None:
        guards = (
            db.query(MenuImportGuard)
            .filter_by(operation_id=operation_id)
            .all()
        )
        if not guards:
            raise RuntimeError("menu_import_guard_missing")
        for guard in guards:
            guard.status = "completed"
            guard.active_key = None
            guard.error_code = None
        db.commit()

    @staticmethod
    def _mark_guards_needs_review(operation_id: str, *, error_code: str) -> None:
        db = get_new_session()
        try:
            guards = (
                db.query(MenuImportGuard)
                .filter_by(operation_id=operation_id)
                .all()
            )
            for guard in guards:
                guard.status = "needs_review"
                guard.error_code = error_code[:120]
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _verify_builder_linkage(
        outcomes,
        *,
        effective_tenant_id: int,
        site_id: str,
        legacy_menu_ids_by_week: dict[tuple[int, int], int],
    ) -> None:
        from .commun_builder_linkage import CommunBuilderMenuLinkService

        expected = set(legacy_menu_ids_by_week)
        actual = {(int(outcome.year), int(outcome.week)) for outcome in outcomes}
        if actual != expected:
            raise RuntimeError("builder_import_week_mismatch")
        service = CommunBuilderMenuLinkService()
        for outcome in outcomes:
            link = service.get_link_for_week(
                tenant_id=effective_tenant_id,
                site_id=site_id,
                year=int(outcome.year),
                week=int(outcome.week),
            )
            expected_legacy_id = legacy_menu_ids_by_week[(int(outcome.year), int(outcome.week))]
            if (
                link is None
                or str(link.builder_menu_id) != str(outcome.menu_id)
                or int(link.legacy_menu_id or 0) != int(expected_legacy_id)
            ):
                raise RuntimeError("builder_linkage_verification_failed")

    def _existing_variant_map(self, db, menu_id: int):
        from .models import MenuVariant

        rows = db.query(MenuVariant).filter_by(menu_id=menu_id).all()
        return {(r.day, r.meal, r.variant_type): r.dish_id for r in rows}

    def _get_or_create_dish(
        self, db, tenant_id: int, site_id: str, item: ImportedMenuItem
    ):
        # Simple exact-name lookup; future: normalization, fragments, fuzzy matching
        existing = (
            db.query(Dish)
            .filter_by(tenant_id=tenant_id, site_id=site_id, name=item.dish_name)
            .first()
        )
        if existing:
            # Backfill category if missing and we imported one
            if not existing.category and item.category:
                existing.category = item.category
            return existing.id
        dish = Dish(
            tenant_id=tenant_id,
            site_id=site_id,
            name=item.dish_name,
            category=item.category,
        )
        db.add(dish)
        db.flush()
        return dish.id
