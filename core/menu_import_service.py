from __future__ import annotations

from typing import Dict

from .db import get_session
from .importers.base import ImportedMenuItem, MenuImportResult
from .menu_service import MenuServiceDB
from .models import Dish


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

    def apply(self, tenant_id: int, result: MenuImportResult) -> Dict:
        summary = []
        db = get_session()
        try:
            for week_block in result.weeks:
                created = 0
                updated = 0
                skipped = 0
                menu = self.menu_service.create_or_get_menu(tenant_id, week_block.week, week_block.year)
                # Preload existing variants map
                existing_map = self._existing_variant_map(db, menu.id)
                for item in week_block.items:
                    dish_id = self._get_or_create_dish(db, tenant_id, item)
                    key = (item.day, item.meal, item.variant_type)
                    prev = existing_map.get(key)
                    if prev == dish_id:
                        skipped += 1
                        continue
                    if prev is None:
                        created += 1
                    else:
                        updated += 1
                    self.menu_service.set_variant(tenant_id, menu.id, item.day, item.meal, item.variant_type, dish_id)
                summary.append({
                    "week": week_block.week,
                    "year": week_block.year,
                    "created": created,
                    "updated": updated,
                    "skipped": skipped,
                    "total": len(week_block.items)
                })
            return {"weeks": summary, "warnings": result.warnings, "errors": result.errors}
        finally:
            db.close()

    def _existing_variant_map(self, db, menu_id: int):
        from .models import MenuVariant
        rows = db.query(MenuVariant).filter_by(menu_id=menu_id).all()
        return {(r.day, r.meal, r.variant_type): r.dish_id for r in rows}

    def _get_or_create_dish(self, db, tenant_id: int, item: ImportedMenuItem):
        # Simple exact-name lookup; future: normalization, fragments, fuzzy matching
        existing = db.query(Dish).filter_by(tenant_id=tenant_id, name=item.dish_name).first()
        if existing:
            # Backfill category if missing and we imported one
            if not existing.category and item.category:
                existing.category = item.category
                db.commit()
            return existing.id
        dish = Dish(tenant_id=tenant_id, name=item.dish_name, category=item.category)
        db.add(dish)
        db.commit()
        db.refresh(dish)
        return dish.id
