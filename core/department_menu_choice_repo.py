from __future__ import annotations

"""Shared repository for explicit department menu choices.

Explicit department menu choices are stored separately from kitchen/Weekview alt2 drift.
No row means no explicit choice. Stored rows represent the shared canonical truth.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from hashlib import sha1
from typing import Sequence

from core.db import get_session
from core.models import DepartmentMenuChoice


_DAY_MAP = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


@dataclass(frozen=True)
class DepartmentMenuChoiceRow:
    tenant_id: int
    site_id: str
    department_id: str
    year: int
    week: int
    weekday: int
    meal: str
    selected_variant: str
    version: int


class MenuChoiceRepo:
    def _ensure_table(self, db) -> None:
        DepartmentMenuChoice.__table__.create(bind=db.bind, checkfirst=True)

    def _normalize_selected_variant(self, selected_alt: str) -> str:
        value = str(selected_alt or "").strip().lower()
        if value in {"alt1", "1"}:
            return "alt1"
        if value in {"alt2", "2"}:
            return "alt2"
        raise ValueError("selected_variant invalid")

    def list_for_department_week(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
    ) -> list[DepartmentMenuChoiceRow]:
        db = get_session()
        try:
            self._ensure_table(db)
            rows = (
                db.query(DepartmentMenuChoice)
                .filter_by(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    department_id=str(department_id),
                    year=int(year),
                    week=int(week),
                )
                .order_by(DepartmentMenuChoice.weekday.asc(), DepartmentMenuChoice.meal.asc(), DepartmentMenuChoice.version.asc())
                .all()
            )
            return [
                DepartmentMenuChoiceRow(
                    tenant_id=int(row.tenant_id),
                    site_id=str(row.site_id),
                    department_id=str(row.department_id),
                    year=int(row.year),
                    week=int(row.week),
                    weekday=int(row.weekday),
                    meal=str(row.meal),
                    selected_variant=str(row.selected_variant),
                    version=int(row.version),
                )
                for row in rows
            ]
        finally:
            db.close()

    def get_signature(self, *, tenant_id: int, site_id: str, department_id: str, year: int, week: int) -> str:
        rows = self.list_for_department_week(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=department_id,
            year=year,
            week=week,
        )
        payload = [
            {
                "weekday": row.weekday,
                "meal": row.meal,
                "selected_variant": row.selected_variant,
                "version": row.version,
            }
            for row in rows
        ]
        sig = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return f'W/"portal-menu-choice:{tenant_id}:{site_id}:{department_id}:{year}-{week}:v{sha1(sig.encode()).hexdigest()[:12]}"'

    def set_choice(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: int,
        selected_alt: str,
        meal: str = "lunch",
    ) -> DepartmentMenuChoiceRow:
        selected_variant = self._normalize_selected_variant(selected_alt)
        db = get_session()
        try:
            self._ensure_table(db)
            existing = (
                db.query(DepartmentMenuChoice)
                .filter_by(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    department_id=str(department_id),
                    year=int(year),
                    week=int(week),
                    weekday=int(weekday),
                    meal=str(meal),
                )
                .first()
            )
            now = datetime.now(UTC)
            if existing is None:
                row = DepartmentMenuChoice(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    department_id=str(department_id),
                    year=int(year),
                    week=int(week),
                    weekday=int(weekday),
                    meal=str(meal),
                    selected_variant=selected_variant,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            else:
                existing.selected_variant = selected_variant
                existing.version = int(existing.version or 0) + 1
                existing.updated_at = now
                row = existing
            db.commit()
            db.refresh(row)
            return DepartmentMenuChoiceRow(
                tenant_id=int(row.tenant_id),
                site_id=str(row.site_id),
                department_id=str(row.department_id),
                year=int(row.year),
                week=int(row.week),
                weekday=int(row.weekday),
                meal=str(row.meal),
                selected_variant=str(row.selected_variant),
                version=int(row.version),
            )
        finally:
            db.close()

    def replace_alt2_days(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        days: Sequence[int],
        meal: str = "lunch",
    ) -> None:
        db = get_session()
        try:
            self.replace_alt2_days_in_session(
                db,
                tenant_id=tenant_id,
                site_id=site_id,
                department_id=department_id,
                year=year,
                week=week,
                days=days,
                meal=meal,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def replace_alt2_days_in_session(
        self,
        db,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        days: Sequence[int],
        meal: str = "lunch",
    ) -> None:
        day_set = {int(day) for day in days}
        self._ensure_table(db)
        now = datetime.now(UTC)
        existing = (
            db.query(DepartmentMenuChoice)
            .filter_by(
                tenant_id=int(tenant_id),
                site_id=str(site_id),
                department_id=str(department_id),
                year=int(year),
                week=int(week),
                meal=str(meal),
            )
            .all()
        )
        existing_by_weekday = {int(row.weekday): row for row in existing}

        for weekday in sorted(day_set):
            row = existing_by_weekday.get(weekday)
            if row is None:
                db.add(
                    DepartmentMenuChoice(
                        tenant_id=int(tenant_id),
                        site_id=str(site_id),
                        department_id=str(department_id),
                        year=int(year),
                        week=int(week),
                        weekday=int(weekday),
                        meal=str(meal),
                        selected_variant="alt2",
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
            elif row.selected_variant != "alt2":
                row.selected_variant = "alt2"
                row.version = int(row.version or 0) + 1
                row.updated_at = now

        for weekday, row in existing_by_weekday.items():
            if weekday not in day_set and str(row.selected_variant) == "alt2":
                db.delete(row)

    def derive_map(self, *, tenant_id: int, site_id: str, department_id: str, year: int, week: int) -> dict[str, str | None]:
        rows = self.list_for_department_week(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=department_id,
            year=year,
            week=week,
        )
        m: dict[str, str | None] = {v: None for v in _DAY_MAP.values()}
        for r in rows:
            wk = int(r.weekday)
            dk = _DAY_MAP.get(wk)
            if dk:
                m[dk] = "Alt2" if r.selected_variant == "alt2" else "Alt1"
        return m


__all__ = ["DepartmentMenuChoiceRow", "MenuChoiceRepo"]