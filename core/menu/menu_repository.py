from __future__ import annotations

from .menu_domain import Menu, MenuDetail

_DAY_ORDER = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}

_MEAL_SLOT_ORDER = {
    "breakfast": 1,
    "lunch": 2,
    "dinner": 3,
    "kvallsmat": 4,
    "dessert": 5,
}


class InMemoryMenuRepository:
    def __init__(self) -> None:
        self._menus: dict[str, Menu] = {}

    def add(self, menu: Menu) -> None:
        if menu.menu_id in self._menus:
            raise ValueError(f"menu already exists: {menu.menu_id}")
        self._menus[menu.menu_id] = menu

    def get(self, menu_id: str) -> Menu | None:
        return self._menus.get(menu_id)

    def list_all(self) -> list[Menu]:
        return list(self._menus.values())

    def update(self, menu: Menu) -> None:
        if menu.menu_id not in self._menus:
            raise ValueError(f"menu not found: {menu.menu_id}")
        self._menus[menu.menu_id] = menu


class InMemoryMenuDetailRepository:
    def __init__(self) -> None:
        self._details: dict[str, MenuDetail] = {}

    def add(self, detail: MenuDetail) -> None:
        if detail.menu_detail_id in self._details:
            raise ValueError(f"menu detail already exists: {detail.menu_detail_id}")
        self._details[detail.menu_detail_id] = detail

    def get(self, detail_id: str) -> MenuDetail | None:
        return self._details.get(detail_id)

    def list_for_menu(self, menu_id: str) -> list[MenuDetail]:
        rows = [detail for detail in self._details.values() if detail.menu_id == menu_id]
        return sorted(rows, key=_detail_sort_key)

    def update(self, detail: MenuDetail) -> None:
        if detail.menu_detail_id not in self._details:
            raise ValueError(f"menu detail not found: {detail.menu_detail_id}")
        self._details[detail.menu_detail_id] = detail

    def remove(self, detail_id: str) -> None:
        if detail_id not in self._details:
            raise ValueError(f"menu detail not found: {detail_id}")
        del self._details[detail_id]


def _detail_sort_key(detail: MenuDetail) -> tuple[int, str, int, str, int, str]:
    day_value = str(detail.day or "").strip().lower()
    meal_value = str(detail.meal_slot or "").strip().lower()
    day_rank = _DAY_ORDER.get(day_value, 999)
    meal_rank = _MEAL_SLOT_ORDER.get(meal_value, 999)
    return (
        day_rank,
        day_value,
        meal_rank,
        meal_value,
        int(detail.sort_order),
        detail.menu_detail_id,
    )
