from __future__ import annotations

"""Menu choice repository abstraction for Department Portal.

Explicit department menu choices are stored separately from kitchen/Weekview alt2 drift.
No row means no explicit choice. Stored rows represent the portal-owned truth.
"""
from dataclasses import dataclass
from datetime import datetime, UTC
import json
from hashlib import sha1
from core.db import get_session
from core.models import DepartmentMenuChoice


_DAY_MAP = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}
_REV_DAY_MAP = {v: k for k, v in _DAY_MAP.items()}


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

__all__ = ["MenuChoiceRepo"]
