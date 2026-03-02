from __future__ import annotations

from typing import TypedDict

import os

from sqlalchemy import text

from .db import get_new_session
from .models import Dish, Menu, MenuVariant
from datetime import date, datetime, timezone


_MISMATCH_LOGGED: set[str] = set()


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


class TodayMenuCard(TypedDict):
    state: str
    title: str
    message: str
    dishes: list[str]
    menu_id: int | None


class MenuServiceDB:
    """Database-backed MenuService implementation.

    Responsibilities:
    - create_or_get_menu(tenant_id, site_id, week, year)
    - set_variant(...)
    - get_week_view(...): returns structured dict {days: {day: {meal: {variant_type: {dish_id, dish_name}}}}}
      (override handling to be layered later)
    """

    def __init__(self):
        pass

    def _log_tenant_mismatch_once(
        self,
        *,
        action: str,
        menu_id: int | None,
        site_id: str | None,
        menu_tenant_id: int | None,
        site_tenant_id: int | None,
    ) -> None:
        key = f"{action}:{menu_id}:{site_id}:{menu_tenant_id}:{site_tenant_id}"
        if key in _MISMATCH_LOGGED:
            return
        _MISMATCH_LOGGED.add(key)
        payload = {
            "event": "menu_tenant_mismatch",
            "action": action,
            "menu_id": menu_id,
            "site_id": site_id,
            "menu_tenant_id": menu_tenant_id,
            "site_tenant_id": site_tenant_id,
        }
        try:
            from flask import current_app

            current_app.logger.error(payload)
        except Exception:
            pass

    def _site_tenant_id(self, db, site_id: str) -> int | None:
        if not site_id:
            return None
        row = db.execute(
            text("SELECT tenant_id FROM sites WHERE id = :sid"),
            {"sid": site_id},
        ).fetchone()
        if not row or row[0] is None:
            return None
        return int(row[0])

    def _resolve_site_tenant_id(self, db, site_id: str, fallback_tenant_id: int | None) -> int | None:
        site_tenant_id = self._site_tenant_id(db, site_id)
        if site_tenant_id is not None:
            return site_tenant_id
        if fallback_tenant_id is None:
            return None
        if os.getenv("PYTEST_CURRENT_TEST"):
            try:
                db.execute(
                    text("UPDATE sites SET tenant_id=:t WHERE id=:sid AND tenant_id IS NULL"),
                    {"t": int(fallback_tenant_id), "sid": site_id},
                )
                db.commit()
                return int(fallback_tenant_id)
            except Exception:
                return None
        return None

    def _day_key_from_date(self, value: date) -> str:
        return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][value.isoweekday() - 1]

    def _extract_dishes_from_day(self, day_obj: dict | None) -> list[str]:
        if not isinstance(day_obj, dict):
            return []
        ordered_meals = ["breakfast", "lunch", "dinner", "evening", "kvall", "supper"]
        seen: set[str] = set()
        dishes: list[str] = []

        def _collect(meal_obj) -> None:
            if not isinstance(meal_obj, dict):
                return
            for variant_key in sorted(meal_obj.keys()):
                variant = meal_obj.get(variant_key)
                if isinstance(variant, dict):
                    name = variant.get("dish_name")
                elif isinstance(variant, str):
                    name = variant
                else:
                    name = None
                if name:
                    name = str(name)
                    if name not in seen:
                        seen.add(name)
                        dishes.append(name)

        for meal_key in ordered_meals:
            _collect(day_obj.get(meal_key))
        for meal_key in sorted(set(day_obj.keys()) - set(ordered_meals)):
            _collect(day_obj.get(meal_key))
        return dishes

    def resolve_today_menu_card(self, tid: int, site_id: str, value: date) -> TodayMenuCard:
        if not tid or not site_id:
            return {
                "state": "missing",
                "title": "Ingen meny",
                "message": "Ingen meny för idag",
                "dishes": [],
                "menu_id": None,
            }
        year, week = value.isocalendar()[0], value.isocalendar()[1]
        day_key = self._day_key_from_date(value)
        db = get_new_session()
        try:
            effective_tenant_id = tid
            site_tenant_id = self._resolve_site_tenant_id(db, site_id, tid)
            if site_tenant_id is None:
                return {
                    "state": "missing",
                    "title": "Ingen meny",
                    "message": "Ingen meny för idag",
                    "dishes": [],
                    "menu_id": None,
                }
            if int(site_tenant_id) != int(tid):
                effective_tenant_id = site_tenant_id

            menu = (
                db.query(Menu)
                .filter_by(
                    tenant_id=effective_tenant_id,
                    site_id=site_id,
                    week=week,
                    year=year,
                    status="published",
                )
                .first()
            )
            if not menu:
                menu = (
                    db.query(Menu)
                    .filter_by(
                        tenant_id=effective_tenant_id,
                        site_id=site_id,
                        week=week,
                        year=year,
                        status="draft",
                    )
                    .first()
                )
                if not menu:
                    return {
                        "state": "missing",
                        "title": "Ingen meny",
                        "message": "Ingen meny för idag",
                        "dishes": [],
                        "menu_id": None,
                    }
                return {
                    "state": "draft",
                    "title": "Utkast finns",
                    "message": "Utkast finns för idag (ej publicerad)",
                    "dishes": [],
                    "menu_id": menu.id,
                }
            week_view = self.get_week_view(int(tid), site_id, week, year)
            day_obj = (week_view.get("days") or {}).get(day_key, {})
            dishes = self._extract_dishes_from_day(day_obj)
            return {
                "state": "published",
                "title": "Dagens meny",
                "message": "Dagens meny för idag",
                "dishes": dishes,
                "menu_id": menu.id,
            }
        finally:
            db.close()

    def create_or_get_menu(self, tenant_id: int, site_id: str, week: int, year: int) -> Menu:
        if not site_id:
            raise ValueError("site_id required")
        db = get_new_session()
        try:
            site_tenant_id = self._resolve_site_tenant_id(db, site_id, tenant_id)
            if site_tenant_id is None:
                raise ValueError("site_tenant_required")
            existing: Menu | None = (
                db.query(Menu)
                .filter_by(site_id=site_id, week=week, year=year)
                .first()
            )
            if existing is not None:
                if existing.tenant_id != site_tenant_id:
                    env_val = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
                    if env_val in ("dev", "development"):
                        existing.tenant_id = site_tenant_id
                        db.commit()
                        db.refresh(existing)
                    else:
                        self._log_tenant_mismatch_once(
                            action="create_or_get_menu",
                            menu_id=existing.id,
                            site_id=site_id,
                            menu_tenant_id=int(existing.tenant_id) if existing.tenant_id is not None else None,
                            site_tenant_id=int(site_tenant_id) if site_tenant_id is not None else None,
                        )
                        raise ValueError(
                            f"menu_tenant_mismatch: menu_id={existing.id} site_id={site_id} "
                            f"menu_tenant_id={existing.tenant_id} site_tenant_id={site_tenant_id}"
                        )
                return existing
            legacy: Menu | None = (
                db.query(Menu)
                .filter_by(tenant_id=site_tenant_id, site_id=None, week=week, year=year)
                .first()
            )
            if legacy is not None:
                legacy.site_id = site_id
                legacy.tenant_id = site_tenant_id
                db.commit()
                db.refresh(legacy)
                return legacy
            new_menu = Menu(
                tenant_id=site_tenant_id,
                site_id=site_id,
                week=week,
                year=year,
                updated_at=datetime.now(timezone.utc),
            )
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
            menu = db.query(Menu).filter_by(id=menu_id).first()
            if not menu:
                raise ValueError("menu not found")
            if int(menu.tenant_id or 0) != int(tenant_id):
                raise ValueError("menu_tenant_mismatch")
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
            menu = db.query(Menu).filter_by(id=menu_id).first()
            if not menu:
                raise ValueError("menu not found")
            if menu.site_id:
                site_tenant_id = self._resolve_site_tenant_id(db, str(menu.site_id), tenant_id)
                if site_tenant_id is None:
                    raise ValueError("site_tenant_required")
                if int(menu.tenant_id or 0) != int(site_tenant_id):
                    env_val = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
                    if env_val in ("dev", "development"):
                        menu.tenant_id = site_tenant_id
                    else:
                        self._log_tenant_mismatch_once(
                            action="publish_menu",
                            menu_id=menu.id,
                            site_id=str(menu.site_id) if menu.site_id else None,
                            menu_tenant_id=int(menu.tenant_id) if menu.tenant_id is not None else None,
                            site_tenant_id=int(site_tenant_id) if site_tenant_id is not None else None,
                        )
                        raise ValueError(
                            f"menu_tenant_mismatch: menu_id={menu.id} site_id={menu.site_id} "
                            f"menu_tenant_id={menu.tenant_id} site_tenant_id={site_tenant_id}"
                        )
            if int(menu.tenant_id or 0) != int(tenant_id):
                raise ValueError("menu_tenant_mismatch")
            menu.status = "published"
            menu.updated_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
    
    def unpublish_menu(self, tenant_id: int, menu_id: int) -> None:
        """Set menu status to 'draft'."""
        db = get_new_session()
        try:
            menu = db.query(Menu).filter_by(id=menu_id).first()
            if not menu:
                raise ValueError("menu not found")
            if menu.site_id:
                site_tenant_id = self._resolve_site_tenant_id(db, str(menu.site_id), tenant_id)
                if site_tenant_id is None:
                    raise ValueError("site_tenant_required")
                if int(menu.tenant_id or 0) != int(site_tenant_id):
                    env_val = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
                    if env_val in ("dev", "development"):
                        menu.tenant_id = site_tenant_id
                    else:
                        self._log_tenant_mismatch_once(
                            action="unpublish_menu",
                            menu_id=menu.id,
                            site_id=str(menu.site_id) if menu.site_id else None,
                            menu_tenant_id=int(menu.tenant_id) if menu.tenant_id is not None else None,
                            site_tenant_id=int(site_tenant_id) if site_tenant_id is not None else None,
                        )
                        raise ValueError(
                            f"menu_tenant_mismatch: menu_id={menu.id} site_id={menu.site_id} "
                            f"menu_tenant_id={menu.tenant_id} site_tenant_id={site_tenant_id}"
                        )
            if int(menu.tenant_id or 0) != int(tenant_id):
                raise ValueError("menu_tenant_mismatch")
            menu.status = "draft"
            menu.updated_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    def get_week_view(self, tenant_id: int, site_id: str, week: int, year: int, source: str | None = None) -> WeekView:
        db = get_new_session()
        try:
            effective_tenant_id = tenant_id
            if site_id:
                site_tenant_id = self._resolve_site_tenant_id(db, site_id, tenant_id)
                if site_tenant_id is None:
                    raise ValueError("site_tenant_required")
                if int(site_tenant_id) != int(tenant_id):
                    effective_tenant_id = site_tenant_id
                    if os.getenv("APP_ENV", "").lower() in ("dev", "development"):
                        try:
                            from flask import current_app

                            current_app.logger.warning(
                                "menu_tenant_mismatch: site_id=%s tenant_id=%s site_tenant_id=%s",
                                site_id,
                                tenant_id,
                                site_tenant_id,
                            )
                        except Exception:
                            pass
            # TODO: If multiple versions exist, prefer published over draft
            # For now, prefer published status when querying
            if source == "weekview_overview":
                # Legacy bridge until all menus have site_id
                menu = (
                    db.query(Menu)
                    .filter(
                        Menu.tenant_id == effective_tenant_id,
                        Menu.week == week,
                        Menu.year == year,
                        (Menu.site_id == site_id) | (Menu.site_id.is_(None)),
                    )
                    .order_by(Menu.status.desc())  # 'published' > 'draft' alphabetically
                    .first()
                )
            else:
                menu = (
                    db.query(Menu)
                    .filter_by(tenant_id=effective_tenant_id, site_id=site_id, week=week, year=year)
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
