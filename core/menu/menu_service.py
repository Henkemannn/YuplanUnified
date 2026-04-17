from __future__ import annotations

from .menu_domain import Menu, MenuDetail
from .menu_repository import InMemoryMenuDetailRepository, InMemoryMenuRepository


class MenuService:
    def __init__(
        self,
        menu_repository: InMemoryMenuRepository | None = None,
        menu_detail_repository: InMemoryMenuDetailRepository | None = None,
        composition_repository: object | None = None,
    ) -> None:
        self._menu_repository = menu_repository or InMemoryMenuRepository()
        self._menu_detail_repository = menu_detail_repository or InMemoryMenuDetailRepository()
        self._composition_repository = composition_repository

    def create_menu(
        self,
        menu_id: str,
        site_id: str,
        week_key: str,
        *,
        version: int = 1,
        status: str = "draft",
    ) -> Menu:
        menu_id_value = str(menu_id or "").strip()
        site_id_value = str(site_id or "").strip()
        week_key_value = str(week_key or "").strip()
        if not menu_id_value:
            raise ValueError("menu_id must be non-empty")
        if not site_id_value:
            raise ValueError("site_id must be non-empty")
        if not week_key_value:
            raise ValueError("week_key must be non-empty")

        menu = Menu(
            menu_id=menu_id_value,
            site_id=site_id_value,
            week_key=week_key_value,
            version=int(version),
            status=str(status or "").strip() or "draft",
        )
        self._menu_repository.add(menu)
        return menu

    def get_menu(self, menu_id: str) -> Menu | None:
        return self._menu_repository.get(menu_id)

    def list_menus(self) -> list[Menu]:
        return self._menu_repository.list_all()

    def add_menu_detail(
        self,
        menu_detail_id: str,
        menu_id: str,
        day: str,
        meal_slot: str,
        composition_ref_type: str,
        *,
        composition_id: str | None = None,
        unresolved_text: str | None = None,
        note: str | None = None,
        sort_order: int = 0,
    ) -> MenuDetail:
        self._require_menu(menu_id)

        detail = self._build_validated_menu_detail(
            menu_detail_id=menu_detail_id,
            menu_id=menu_id,
            day=day,
            meal_slot=meal_slot,
            composition_ref_type=composition_ref_type,
            composition_id=composition_id,
            unresolved_text=unresolved_text,
            note=note,
            sort_order=sort_order,
        )
        self._menu_detail_repository.add(detail)
        return detail

    def update_menu_detail(
        self,
        menu_detail_id: str,
        *,
        day: str | None = None,
        meal_slot: str | None = None,
        composition_ref_type: str | None = None,
        composition_id: str | None = None,
        unresolved_text: str | None = None,
        note: str | None = None,
        sort_order: int | None = None,
    ) -> MenuDetail:
        current = self._menu_detail_repository.get(menu_detail_id)
        if current is None:
            raise ValueError(f"menu detail not found: {menu_detail_id}")

        detail = self._build_validated_menu_detail(
            menu_detail_id=current.menu_detail_id,
            menu_id=current.menu_id,
            day=current.day if day is None else day,
            meal_slot=current.meal_slot if meal_slot is None else meal_slot,
            composition_ref_type=current.composition_ref_type
            if composition_ref_type is None
            else composition_ref_type,
            composition_id=current.composition_id if composition_id is None else composition_id,
            unresolved_text=current.unresolved_text
            if unresolved_text is None
            else unresolved_text,
            note=current.note if note is None else note,
            sort_order=current.sort_order if sort_order is None else sort_order,
        )
        self._menu_detail_repository.update(detail)
        return detail

    def remove_menu_detail(self, menu_detail_id: str) -> None:
        self._menu_detail_repository.remove(menu_detail_id)

    def list_menu_details(self, menu_id: str) -> list[MenuDetail]:
        self._require_menu(menu_id)
        return self._menu_detail_repository.list_for_menu(menu_id)

    def _require_menu(self, menu_id: str) -> Menu:
        menu_id_value = str(menu_id or "").strip()
        if not menu_id_value:
            raise ValueError("menu_id must be non-empty")

        menu = self._menu_repository.get(menu_id_value)
        if menu is None:
            raise ValueError(f"menu not found: {menu_id_value}")
        return menu

    def _build_validated_menu_detail(
        self,
        *,
        menu_detail_id: str,
        menu_id: str,
        day: str,
        meal_slot: str,
        composition_ref_type: str,
        composition_id: str | None,
        unresolved_text: str | None,
        note: str | None,
        sort_order: int,
    ) -> MenuDetail:
        menu_detail_id_value = str(menu_detail_id or "").strip()
        if not menu_detail_id_value:
            raise ValueError("menu_detail_id must be non-empty")

        menu_id_value = str(menu_id or "").strip()
        if not menu_id_value:
            raise ValueError("menu_id must be non-empty")

        day_value = str(day or "").strip()
        meal_slot_value = str(meal_slot or "").strip()
        ref_type_value = str(composition_ref_type or "").strip().lower()
        if ref_type_value not in {"composition", "unresolved"}:
            raise ValueError("composition_ref_type must be 'composition' or 'unresolved'")

        composition_id_value = str(composition_id or "").strip() or None
        unresolved_text_value = str(unresolved_text or "").strip() or None

        if ref_type_value == "composition":
            if composition_id_value is None:
                raise ValueError("composition_id is required when composition_ref_type='composition'")
            if unresolved_text_value is not None:
                raise ValueError(
                    "unresolved_text must be empty when composition_ref_type='composition'"
                )
            if self._composition_repository is not None:
                composition = self._composition_repository.get(composition_id_value)
                if composition is None:
                    raise ValueError(f"composition not found: {composition_id_value}")
        else:
            if unresolved_text_value is None:
                raise ValueError("unresolved_text is required when composition_ref_type='unresolved'")
            if composition_id_value is not None:
                raise ValueError(
                    "composition_id must be empty when composition_ref_type='unresolved'"
                )

        return MenuDetail(
            menu_detail_id=menu_detail_id_value,
            menu_id=menu_id_value,
            day=day_value,
            meal_slot=meal_slot_value,
            composition_ref_type=ref_type_value,
            composition_id=composition_id_value,
            unresolved_text=unresolved_text_value,
            note=str(note).strip() if note is not None else None,
            sort_order=int(sort_order),
        )
