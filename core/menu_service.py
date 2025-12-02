from __future__ import annotations

from typing import TypedDict

from .db import get_new_session
from .models import Dish, Menu, MenuVariant
from datetime import datetime, timezone


class _VariantInfo(TypedDict, total=False):
    dish_id: int | None
    dish_name: str | None


class _DayMealVariants(TypedDict):
    # variant_type -> variant info
    # We can't know variant type keys statically (e.g., 'standard', 'veg') so map of str
    __root__: dict[str, _VariantInfo]  # marker not accessed directly; used for documentation


class WeekView(TypedDict):
    menu_id: int | None
    days: dict[str, dict[str, dict[str, _VariantInfo]]]


class MenuServiceDB:
    """Database-backed MenuService implementation.

    Responsibilities:
    - create_or_get_menu(tenant_id, week, year)
    - set_variant(...)
    - get_week_view(...): returns structured dict {days: {day: {meal: {variant_type: {dish_id, dish_name}}}}}
      (override handling to be layered later)
    """

    def __init__(self):
        pass

    def create_or_get_menu(self, tenant_id: int, week: int, year: int) -> Menu:
        db = get_new_session()
        try:
            existing: Menu | None = (
                db.query(Menu).filter_by(tenant_id=tenant_id, week=week, year=year).first()
            )
            if existing is not None:
                return existing
            new_menu = Menu(tenant_id=tenant_id, week=week, year=year, updated_at=datetime.now(timezone.utc))
            db.add(new_menu)
            db.commit()
            db.refresh(new_menu)
            return new_menu
        finally:
            db.close()

    def set_variant(
        self,
        tenant_id: int,
        menu_id: int,
        day: str,
        meal: str,
        variant_type: str,
        dish_id: int | None,
    ) -> int:
        day = day.strip()
        meal = meal.strip()
        variant_type = variant_type.strip()
        db = get_new_session()
        try:
            # validate menu belongs to tenant
            menu = db.query(Menu).filter_by(id=menu_id, tenant_id=tenant_id).first()
            if not menu:
                raise ValueError("menu not found for tenant")
            mv = (
                db.query(MenuVariant)
                .filter_by(menu_id=menu_id, day=day, meal=meal, variant_type=variant_type)
                .first()
            )
            if mv:
                mv.dish_id = dish_id
            else:
                mv = MenuVariant(
                    menu_id=menu_id, day=day, meal=meal, variant_type=variant_type, dish_id=dish_id
                )
                db.add(mv)
            db.commit()
            return mv.id
        finally:
            db.close()

    def publish_menu(self, tenant_id: int, menu_id: int) -> None:
        """Set menu status to 'published'."""
        db = get_new_session()
        try:
            menu = db.query(Menu).filter_by(id=menu_id, tenant_id=tenant_id).first()
            if not menu:
                raise ValueError("menu not found for tenant")
            menu.status = "published"
            menu.updated_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
    
    def unpublish_menu(self, tenant_id: int, menu_id: int) -> None:
        """Set menu status to 'draft'."""
        db = get_new_session()
        try:
            menu = db.query(Menu).filter_by(id=menu_id, tenant_id=tenant_id).first()
            if not menu:
                raise ValueError("menu not found for tenant")
            menu.status = "draft"
            menu.updated_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    def get_week_view(self, tenant_id: int, week: int, year: int) -> WeekView:
        db = get_new_session()
        try:
            # TODO: If multiple versions exist, prefer published over draft
            # For now, prefer published status when querying
            menu = (
                db.query(Menu)
                .filter_by(tenant_id=tenant_id, week=week, year=year)
                .order_by(Menu.status.desc())  # 'published' > 'draft' alphabetically
                .first()
            )
            if not menu:
                return {"menu_id": None, "menu_status": None, "updated_at": None, "days": {}}  # type: ignore[return-value]
            # Ensure updated_at populated (older seed data may have NULL)
            if menu.updated_at is None:
                menu.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(menu)
            variants = (
                db.query(MenuVariant, Dish)
                .join(Dish, Dish.id == MenuVariant.dish_id, isouter=True)
                .filter(MenuVariant.menu_id == menu.id)
                .all()
            )
            structure: dict[str, dict[str, dict[str, _VariantInfo]]] = {}
            for mv, dish in variants:
                structure.setdefault(mv.day, {}).setdefault(mv.meal, {})[mv.variant_type] = {
                    "dish_id": mv.dish_id,
                    "dish_name": dish.name if dish else None,
                }
            return {"menu_id": menu.id, "menu_status": menu.status, "updated_at": menu.updated_at, "days": structure}  # type: ignore[return-value]
        finally:
            db.close()
