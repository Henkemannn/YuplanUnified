"""Service layer stubs.
Each service will later include full logic + SQLAlchemy session injection.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol


class MenuService(Protocol):  # pragma: no cover - interface stub
    def get_menu_for_week(self, tenant_id: int, week: int, year: int): ...
    def set_variant(
        self,
        tenant_id: int,
        menu_id: int,
        day: str,
        meal: str,
        variant_type: str,
        dish_id: int | None,
    ): ...


class SchedulingService(Protocol):
    def generate(self, tenant_id: int, strategy: str, **params): ...
    def list_slots(self, tenant_id: int, start: date, end: date): ...


class MetricsService(Protocol):
    def log(self, tenant_id: int, payload: dict): ...
    def recommend(self, tenant_id: int, guest_count: int, categories: list[str]): ...


class DietService(Protocol):
    def assign_diet(self, unit_id: int, diet_type_id: int, count: int): ...
    def mark_selection(self, unit_id: int, day: str, meal: str, diet_type_id: int): ...


class ReportingService(Protocol):
    def menu_distribution(self, tenant_id: int, week: int, year: int): ...


# Concrete minimal placeholder implementations
class InMemoryMenuService:
    def __init__(self):
        self._store = {}

    def get_menu_for_week(self, tenant_id: int, week: int, year: int):  # simple placeholder
        return self._store.get((tenant_id, year, week), {})

    def set_variant(
        self,
        tenant_id: int,
        menu_id: int,
        day: str,
        meal: str,
        variant_type: str,
        dish_id: int | None,
    ):
        key = (tenant_id, menu_id)
        self._store.setdefault(key, []).append(
            {"day": day, "meal": meal, "variant": variant_type, "dish": dish_id}
        )
