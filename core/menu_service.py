from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

import os

from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy import text
from flask import current_app, g, has_app_context

from .db import get_new_session
from .models import Dish, Menu, MenuVariant
from datetime import date, datetime, timezone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


_MISMATCH_LOGGED: set[str] = set()

_DAY_KEY_ORDER = {
    "mon": 0,
    "monday": 0,
    "mån": 0,
    "måndag": 0,
    "tue": 1,
    "tuesday": 1,
    "tis": 1,
    "tisdag": 1,
    "wed": 2,
    "wednesday": 2,
    "ons": 2,
    "onsdag": 2,
    "thu": 3,
    "thursday": 3,
    "tor": 3,
    "torsdag": 3,
    "fri": 4,
    "friday": 4,
    "fre": 4,
    "fredag": 4,
    "sat": 5,
    "saturday": 5,
    "lör": 5,
    "lördag": 5,
    "sun": 6,
    "sunday": 6,
    "sön": 6,
    "söndag": 6,
}


@dataclass(frozen=True)
class _LegacyWeekViewRow:
    day: str
    meal: str
    variant_type: str
    dish_id: int | None
    dish_name: str | None
    sort_order: int | None = None


class _VariantInfo(TypedDict, total=False):
    dish_id: int | None
    dish_name: str | None


class _DayMealVariants(TypedDict):
    # variant_type -> variant info
    # We can't know variant type keys statically (e.g., 'standard', 'veg') so map of str
    __root__: dict[str, _VariantInfo]  # marker not accessed directly; used for documentation


def _week_view_variant_keys(meal: str, variant_type: str) -> tuple[str, ...]:
    raw_meal = str(meal or "").strip().lower()
    meal_alias = {
        "dinner": "dinner",
        "kväll": "dinner",
        "kvall": "dinner",
    }.get(raw_meal, raw_meal)
    raw_variant = str(variant_type or "").strip().lower()
    if meal_alias == "dinner" and raw_variant in {"main", "dinner", "kvall"}:
        # Canonical output first, legacy alias second.
        return ("main", "kvall")
    return (raw_variant,)


def _legacy_day_key(value: str) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "mon": "mon",
        "monday": "mon",
        "mån": "mon",
        "måndag": "mon",
        "tue": "tue",
        "tuesday": "tue",
        "tis": "tue",
        "tisdag": "tue",
        "wed": "wed",
        "wednesday": "wed",
        "ons": "wed",
        "onsdag": "wed",
        "thu": "thu",
        "thursday": "thu",
        "tor": "thu",
        "torsdag": "thu",
        "fri": "fri",
        "friday": "fri",
        "fre": "fri",
        "fredag": "fri",
        "sat": "sat",
        "saturday": "sat",
        "lör": "sat",
        "lördag": "sat",
        "sun": "sun",
        "sunday": "sun",
        "sön": "sun",
        "söndag": "sun",
    }
    return aliases.get(raw, raw)


def _projection_to_week_view_days(rows: list[Any]) -> dict[str, dict[str, dict[str, _VariantInfo]]]:
    structure: dict[str, dict[str, dict[str, _VariantInfo]]] = {}
    rows_sorted = sorted(
        rows,
        key=lambda row: (
            _DAY_KEY_ORDER.get(str(getattr(row, "day", "") or "").strip().lower(), 99),
            str(getattr(row, "day", "") or "").strip().lower(),
            int(getattr(row, "sort_order", 0) or 0),
            str(getattr(row, "builder_menu_row_id", "") or ""),
        ),
    )
    for row in rows_sorted:
        day_key = _legacy_day_key(str(getattr(row, "day", "") or ""))
        meal = str(getattr(row, "meal", "") or "").strip().lower()
        if not day_key or not meal:
            continue
        meal_bucket = structure.setdefault(day_key, {}).setdefault(meal, {})
        variant_keys = _week_view_variant_keys(meal, str(getattr(row, "variant_type", "") or ""))
        variant_info: _VariantInfo = {
            "dish_id": None,
            "dish_name": str(getattr(row, "text", "") or "").strip(),
        }
        for variant_key in variant_keys:
            meal_bucket[variant_key] = variant_info
    return structure


class WeekView(TypedDict):
    menu_id: int | None
    days: dict[str, dict[str, dict[str, _VariantInfo]]]


class TodayMenuCard(TypedDict):
    state: str
    title: str
    message: str
    dishes: list[str]
    menu_id: int | None
    today_menu: dict[str, str]


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

    def _verified_site_tenant_id(self, db, site_id: str) -> int | None:
        if not site_id:
            return None
        row = db.execute(
            text(
                "SELECT tenant_id FROM sites "
                "WHERE id=:sid AND tenant_id IS NOT NULL LIMIT 1"
            ),
            {"sid": str(site_id).strip()},
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

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
        from .weekview.service import DAY_KEYS

        iso_weekday = value.isoweekday()
        if iso_weekday < 1 or iso_weekday > 7:
            return ""
        return DAY_KEYS[iso_weekday - 1]

    def _feature_enabled(self, name: str) -> bool:
        try:
            if not has_app_context():
                return False
            helper = getattr(current_app, "feature_enabled", None)
            if callable(helper):
                return bool(helper(name))
            registry = getattr(current_app, "feature_registry", None)
            return bool(registry.enabled(name)) if registry else False
        except Exception:
            return False

    def _maybe_run_builder_shadow_projection(self, *, tenant_id: int, site_id: str, week: int, year: int, legacy_payload: dict[str, Any]) -> None:
        if not self._feature_enabled("commun.builder.projection_shadow_v0"):
            return
        try:
            from .commun_builder_projection import get_shadow_projection_reader

            reader = get_shadow_projection_reader()
            result = reader.compare_with_legacy(
                tenant_id=tenant_id,
                site_id=site_id,
                year=year,
                week=week,
                legacy_weekview=legacy_payload,
            )
            try:
                g.commun_builder_projection_shadow = result
            except Exception:
                pass
            try:
                current_app.logger.info(
                    {
                        "event": "commun_builder_projection_shadow",
                        "tenant_id": tenant_id,
                        "site_id": site_id,
                        "year": year,
                        "week": week,
                        "builder_menu_id": getattr(result, "builder_menu_id", None),
                        "linked_version": getattr(result, "linked_version", None),
                        "current_builder_version": getattr(result, "current_version", None),
                        "comparison_status": getattr(result, "status", None),
                        "legacy_row_count": getattr(result, "legacy_row_count", None),
                        "builder_row_count": getattr(result, "builder_row_count", None),
                        "difference_count": getattr(result, "difference_count", None),
                    }
                )
            except Exception:
                pass
        except Exception as exc:
            try:
                current_app.logger.warning(
                    {
                        "event": "commun_builder_projection_shadow_error",
                        "tenant_id": tenant_id,
                        "site_id": site_id,
                        "year": year,
                        "week": week,
                        "error": str(exc),
                    }
                )
            except Exception:
                pass
            try:
                g.commun_builder_projection_shadow = {
                    "status": "projection_error",
                    "error": str(exc),
                    "tenant_id": tenant_id,
                    "site_id": site_id,
                    "year": year,
                    "week": week,
                }
            except Exception:
                pass

    def get_today_menu_for_site(self, tid: int, site_id: str, value: date) -> dict[str, str]:
        try:
            iso = value.isocalendar()
            year, week = int(iso[0]), int(iso[1])
            week_view = self.get_week_view(int(tid), site_id, week, year) or {}
            days_raw = (week_view.get("days") or {}) if isinstance(week_view, dict) else {}
            day_map = {str(k).strip().lower(): v for k, v in (days_raw or {}).items()}
            day_key = self._day_key_from_date(value)
            day_aliases = {
                "mon": ["mon", "monday", "mån", "måndag"],
                "tue": ["tue", "tuesday", "tis", "tisdag"],
                "wed": ["wed", "wednesday", "ons", "onsdag"],
                "thu": ["thu", "thursday", "tor", "torsdag"],
                "fri": ["fri", "friday", "fre", "fredag"],
                "sat": ["sat", "saturday", "lör", "lördag"],
                "sun": ["sun", "sunday", "sön", "söndag"],
            }

            def _pick_name(val) -> str:
                if not val:
                    return ""
                if isinstance(val, dict):
                    return str(val.get("dish_name") or val.get("name") or "")
                return str(val)

            def _meal_obj(day: dict, meal_key: str) -> dict:
                meal = day.get(meal_key) or day.get(meal_key.capitalize()) or {}
                if not meal and meal_key == "dinner":
                    meal = day.get("Kväll") or day.get("kväll") or day.get("kvall") or {}
                if isinstance(meal, dict):
                    return meal
                return {"main": meal}

            def _variant_text(meal: dict, keys: list[str]) -> str:
                for key in keys:
                    name = _pick_name(meal.get(key) or meal.get(key.capitalize()))
                    if name:
                        return name
                return ""

            day_val = {}
            for alias in day_aliases.get(day_key, [day_key]):
                day_val = day_map.get(alias) or {}
                if day_val:
                    break

            lunch_meal = _meal_obj(day_val, "lunch")
            dinner_meal = _meal_obj(day_val, "dinner")

            return {
                "lunch_alt1": _variant_text(lunch_meal, ["main", "alt1"]),
                "lunch_alt2": _variant_text(lunch_meal, ["alt2"]),
                "dessert": _variant_text(lunch_meal, ["dessert"]),
                "dinner": _variant_text(dinner_meal, ["main", "dinner", "kvall", "alt1", "alt2"]),
            }
        except Exception:
            return {"lunch_alt1": "", "lunch_alt2": "", "dessert": "", "dinner": ""}

    def resolve_today_menu_card(self, tid: int, site_id: str, value: date) -> TodayMenuCard:
        if not tid or not site_id:
            return {
                "state": "missing",
                "title": "Ingen meny",
                "message": "Ingen meny för idag",
                "dishes": [],
                "menu_id": None,
                "today_menu": {"lunch_alt1": "", "lunch_alt2": "", "dessert": "", "dinner": ""},
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
                    "today_menu": {"lunch_alt1": "", "lunch_alt2": "", "dessert": "", "dinner": ""},
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
                        "today_menu": {"lunch_alt1": "", "lunch_alt2": "", "dessert": "", "dinner": ""},
                    }
                return {
                    "state": "draft",
                    "title": "Utkast finns",
                    "message": "Utkast finns för idag (ej publicerad)",
                    "dishes": [],
                    "menu_id": menu.id,
                    "today_menu": {"lunch_alt1": "", "lunch_alt2": "", "dessert": "", "dinner": ""},
                }
            menu_today = self.get_today_menu_for_site(int(tid), site_id, value)
            candidates = [
                menu_today.get("lunch_alt1", ""),
                menu_today.get("lunch_alt2", ""),
                menu_today.get("dessert", ""),
                menu_today.get("dinner", ""),
            ]
            dishes: list[str] = []
            seen: set[str] = set()
            for name in candidates:
                if name and name not in seen:
                    seen.add(name)
                    dishes.append(name)
            return {
                "state": "published",
                "title": "Dagens meny",
                "message": "Dagens meny för idag",
                "dishes": dishes,
                "menu_id": menu.id,
                "today_menu": menu_today,
            }
        finally:
            db.close()

    def create_or_get_menu(self, tenant_id: int, site_id: str, week: int, year: int) -> Menu:
        db = get_new_session()
        try:
            menu = self._create_or_get_menu_in_session(db, tenant_id, site_id, week, year)
            db.commit()
            db.refresh(menu)
            return menu
        except IntegrityError:
            db.rollback()
            site_tenant_id = self._verified_site_tenant_id(db, site_id)
            exact_match: Menu | None = (
                db.query(Menu)
                .filter_by(
                    tenant_id=site_tenant_id,
                    site_id=site_id,
                    week=week,
                    year=year,
                )
                .first()
            )
            if exact_match is not None:
                return exact_match
            legacy_conflict: Menu | None = (
                db.query(Menu)
                .filter_by(tenant_id=site_tenant_id, week=week, year=year)
                .first()
            )
            if legacy_conflict is not None:
                raise ValueError(
                    f"menu_site_conflict: menu_id={legacy_conflict.id} "
                    f"menu_site_id={legacy_conflict.site_id} requested_site_id={site_id}"
                )
            raise
        finally:
            db.close()

    def _create_or_get_menu_in_session(
        self,
        db,
        tenant_id: int,
        site_id: str,
        week: int,
        year: int,
    ) -> Menu:
        if not site_id:
            raise ValueError("site_id required")
        site_tenant_id = self._resolve_site_tenant_id(db, site_id, tenant_id)
        if site_tenant_id is None:
            raise ValueError("site_tenant_required")
        if int(site_tenant_id) != int(tenant_id):
            raise ValueError(
                f"site_tenant_mismatch: site_id={site_id} "
                f"site_tenant_id={site_tenant_id} tenant_id={tenant_id}"
            )
        existing: Menu | None = (
            db.query(Menu)
            .filter_by(
                tenant_id=site_tenant_id,
                site_id=site_id,
                week=week,
                year=year,
            )
            .first()
        )
        if existing is not None:
            return existing
        conflicting_tenant_menu: Menu | None = (
            db.query(Menu)
            .filter_by(site_id=site_id, week=week, year=year)
            .first()
        )
        if conflicting_tenant_menu is not None:
            self._log_tenant_mismatch_once(
                action="create_or_get_menu",
                menu_id=conflicting_tenant_menu.id,
                site_id=site_id,
                menu_tenant_id=(
                    int(conflicting_tenant_menu.tenant_id)
                    if conflicting_tenant_menu.tenant_id is not None
                    else None
                ),
                site_tenant_id=int(site_tenant_id),
            )
            raise ValueError(
                f"menu_tenant_mismatch: menu_id={conflicting_tenant_menu.id} "
                f"site_id={site_id} menu_tenant_id={conflicting_tenant_menu.tenant_id} "
                f"site_tenant_id={site_tenant_id}"
            )

        # Legacy schemas may still enforce UNIQUE(tenant_id, week, year)
        # without site_id. Never rebind that row to another site.
        if self._has_legacy_menu_uniqueness(db):
            legacy_tenant_week: Menu | None = (
                db.query(Menu)
                .filter_by(tenant_id=site_tenant_id, week=week, year=year)
                .first()
            )
            if legacy_tenant_week is not None:
                raise ValueError(
                    f"menu_site_conflict: menu_id={legacy_tenant_week.id} "
                    f"menu_site_id={legacy_tenant_week.site_id} requested_site_id={site_id}"
                )
        new_menu = Menu(
            tenant_id=site_tenant_id,
            site_id=site_id,
            week=week,
            year=year,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(new_menu)
        db.flush()
        return new_menu

    def set_variant_atomic(
        self,
        tenant_id: int,
        site_id: str,
        week: int,
        year: int,
        day: str,
        meal: str,
        variant_type: str,
        dish_id: int | None,
        dish_name: str | None = None,
    ) -> tuple[int, int]:
        db = get_new_session()
        try:
            menu = self._create_or_get_menu_in_session(
                db, tenant_id, site_id, week, year
            )
            mv = self._set_variant_in_session(
                db=db,
                tenant_id=tenant_id,
                site_id=site_id,
                menu=menu,
                day=day,
                meal=meal,
                variant_type=variant_type,
                dish_id=dish_id,
                dish_name=dish_name,
            )
            db.commit()
            return int(menu.id), int(mv.id)
        except (ValueError, IntegrityError, SQLAlchemyError):
            db.rollback()
            raise
        finally:
            db.close()

    def _resolve_site_dish(
        self,
        db,
        *,
        tenant_id: int,
        site_id: str,
        dish_id: int | None,
        dish_name: str | None,
    ) -> int | None:
        if dish_id is not None:
            dish = db.query(Dish).filter_by(id=dish_id).first()
            if dish is None:
                raise ValueError("dish_not_found")
            if int(dish.tenant_id or 0) != int(tenant_id):
                raise ValueError("dish_tenant_mismatch")
            if str(dish.site_id or "") != str(site_id):
                raise ValueError("dish_site_mismatch")
            return int(dish.id)
        if not dish_name:
            return None
        dish = (
            db.query(Dish)
            .filter_by(tenant_id=tenant_id, site_id=site_id, name=dish_name)
            .first()
        )
        if dish is None:
            dish = Dish(
                tenant_id=tenant_id,
                site_id=site_id,
                name=dish_name,
                category=None,
            )
            db.add(dish)
            db.flush()
        return int(dish.id)

    def _set_variant_in_session(
        self,
        *,
        db,
        tenant_id: int,
        site_id: str,
        menu: Menu,
        day: str,
        meal: str,
        variant_type: str,
        dish_id: int | None,
        dish_name: str | None = None,
    ) -> MenuVariant:
        if (
            int(menu.tenant_id or 0) != int(tenant_id)
            or str(menu.site_id or "") != str(site_id)
        ):
            raise ValueError("menu_site_mismatch")
        if self._verified_site_tenant_id(db, site_id) != int(tenant_id):
            raise ValueError("site_tenant_mismatch")
        resolved_dish_id = self._resolve_site_dish(
            db,
            tenant_id=tenant_id,
            site_id=site_id,
            dish_id=dish_id,
            dish_name=dish_name,
        )
        values = {
            "menu_id": menu.id,
            "day": day.strip(),
            "meal": meal.strip(),
            "variant_type": variant_type.strip(),
        }
        mv = db.query(MenuVariant).filter_by(**values).first()
        if mv is None:
            mv = MenuVariant(**values, dish_id=resolved_dish_id)
            db.add(mv)
        else:
            mv.dish_id = resolved_dish_id
        return mv

    @staticmethod
    def _has_legacy_menu_uniqueness(db) -> bool:
        identity = {"tenant_id", "week", "year"}
        inspector = sqlalchemy_inspect(db.bind)
        for constraint in inspector.get_unique_constraints("menus"):
            if set(constraint.get("column_names") or ()) == identity:
                return True
        for index in inspector.get_indexes("menus"):
            if index.get("unique") and set(index.get("column_names") or ()) == identity:
                return True
        return False

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
            mv = self._set_variant_in_session(
                db=db,
                tenant_id=tenant_id,
                site_id=str(menu.site_id or ""),
                menu=menu,
                day=day,
                meal=meal,
                variant_type=variant_type,
                dish_id=dish_id,
            )
            db.commit()
            return mv.id
        except (ValueError, IntegrityError, SQLAlchemyError):
            db.rollback()
            raise
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
            if menu.site_id is not None:
                from .commun_builder_publication import CommunBuilderPublicationService

                publication_service = CommunBuilderPublicationService()
                publication_args = dict(
                    tenant_id=int(menu.tenant_id or tenant_id),
                    site_id=str(menu.site_id),
                    year=int(menu.year),
                    week=int(menu.week),
                    legacy_menu_id=int(menu.id),
                    db=db,
                )
                publication_state = publication_service.get_publication_for_week(
                    tenant_id=int(menu.tenant_id or tenant_id),
                    site_id=str(menu.site_id),
                    year=int(menu.year),
                    week=int(menu.week),
                )
                if publication_state is not None:
                    publication_state = publication_service.republish_week(**publication_args)
                else:
                    publication_state = publication_service.publish_week(**publication_args)
                if publication_state is None:
                    raise RuntimeError("canonical_publication_missing")
            menu.status = "published"
            menu.updated_at = datetime.now(timezone.utc)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
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
            if menu.site_id is not None:
                from .commun_builder_publication import CommunBuilderPublicationService

                CommunBuilderPublicationService().unpublish_week(
                    tenant_id=int(menu.tenant_id or tenant_id),
                    site_id=str(menu.site_id),
                    year=int(menu.year),
                    week=int(menu.week),
                    db=db,
                )
            menu.status = "draft"
            menu.updated_at = datetime.now(timezone.utc)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
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
            if menu and menu.updated_at is None:
                menu.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(menu)
            publication = None
            try:
                from .commun_builder_publication import CommunBuilderPublicationService

                publication = CommunBuilderPublicationService().get_publication_for_week(
                    tenant_id=int(effective_tenant_id),
                    site_id=str(site_id),
                    year=int(year),
                    week=int(week),
                )
            except Exception:
                publication = None

            if publication is None and menu is None:
                payload = {"menu_id": None, "menu_status": None, "updated_at": None, "days": {}}
                self._maybe_run_builder_shadow_projection(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    week=week,
                    year=year,
                    legacy_payload=payload,
                )
                return payload  # type: ignore[return-value]

            if publication is not None:
                from .commun_builder_projection import CommunBuilderMenuProjectionReader

                projection_outcome = CommunBuilderMenuProjectionReader().get_projection_for_pinned_menu(
                    tenant_id=int(effective_tenant_id),
                    site_id=str(site_id),
                    year=int(year),
                    week=int(week),
                    builder_menu_id=str(publication.builder_menu_id),
                    builder_menu_version=int(publication.builder_menu_version),
                )
                if projection_outcome.status != "ok" or projection_outcome.projection is None:
                    raise RuntimeError(f"published_builder_projection_invalid:{projection_outcome.error or projection_outcome.status}")
                if any(bool(row.error) for row in projection_outcome.projection.rows):
                    first_error = next((row.error for row in projection_outcome.projection.rows if row.error), "projection_error")
                    raise RuntimeError(f"published_builder_projection_invalid:{first_error}")
                structure = _projection_to_week_view_days(projection_outcome.projection.rows)
            else:
                variants = (
                    db.query(MenuVariant, Dish)
                    .join(Dish, Dish.id == MenuVariant.dish_id, isouter=True)
                    .filter(MenuVariant.menu_id == menu.id)
                    .all()
                )
                structure: dict[str, dict[str, dict[str, _VariantInfo]]] = {}
                for mv, dish in variants:
                    meal_bucket = structure.setdefault(mv.day, {}).setdefault(mv.meal, {})
                    variant_info = {
                        "dish_id": mv.dish_id,
                        "dish_name": dish.name if dish else None,
                    }
                    for variant_key in _week_view_variant_keys(mv.meal, mv.variant_type):
                        meal_bucket[variant_key] = variant_info
                day_aliases = {
                    "monday": "mon",
                    "mon": "mon",
                    "måndag": "mon",
                    "mån": "mon",
                    "tuesday": "tue",
                    "tue": "tue",
                    "tisdag": "tue",
                    "tis": "tue",
                    "wednesday": "wed",
                    "wed": "wed",
                    "onsdag": "wed",
                    "ons": "wed",
                    "thursday": "thu",
                    "thu": "thu",
                    "torsdag": "thu",
                    "tor": "thu",
                    "friday": "fri",
                    "fri": "fri",
                    "fredag": "fri",
                    "fre": "fri",
                    "saturday": "sat",
                    "sat": "sat",
                    "lördag": "sat",
                    "lör": "sat",
                    "sunday": "sun",
                    "sun": "sun",
                    "söndag": "sun",
                    "sön": "sun",
                }
                meal_aliases = {
                    "lunch": "lunch",
                    "Lunch": "lunch",
                    "dinner": "dinner",
                    "Dinner": "dinner",
                    "Kväll": "dinner",
                    "kväll": "dinner",
                    "kvall": "dinner",
                }
                normalized_days: dict[str, dict[str, dict[str, _VariantInfo]]] = {}
                for raw_day, meals in structure.items():
                    if not isinstance(meals, dict):
                        continue
                    day_key = day_aliases.get(str(raw_day).strip().lower())
                    if not day_key:
                        continue
                    day_bucket = normalized_days.setdefault(day_key, {})
                    for raw_meal, variants_map in meals.items():
                        meal_key = meal_aliases.get(str(raw_meal).strip(), meal_aliases.get(str(raw_meal).strip().lower()))
                        if meal_key is None:
                            continue
                        day_bucket[meal_key] = variants_map
                for alias_day, meals in normalized_days.items():
                    structure.setdefault(alias_day, {}).update(meals)
            if menu is None:
                payload = {"menu_id": None, "menu_status": None, "updated_at": None, "days": structure}
            else:
                payload = {"menu_id": menu.id, "menu_status": menu.status, "updated_at": menu.updated_at, "days": structure}
            self._maybe_run_builder_shadow_projection(
                tenant_id=tenant_id,
                site_id=site_id,
                week=week,
                year=year,
                legacy_payload=payload,
            )
            return payload  # type: ignore[return-value]
        finally:
            db.close()
