from __future__ import annotations

from typing import Any

from sqlalchemy import text

from .diet_family import DIET_FAMILY_OTHER
from .db import get_session
from .diet_scope import DietaryReferenceError
from .models import DietaryType, Unit, UnitDietAssignment


class DietService:
    def __init__(self):
        pass

    @staticmethod
    def _require_site_scope(db, tenant_id: int, site_id: str) -> str:
        normalized_site_id = str(site_id or "").strip()
        if not normalized_site_id or not db.execute(
            text("SELECT 1 FROM sites WHERE id=:site_id AND tenant_id=:tenant_id"),
            {"site_id": normalized_site_id, "tenant_id": tenant_id},
        ).first():
            raise DietaryReferenceError("site_scope_mismatch", 403)
        return normalized_site_id

    def list_assignments(self, unit_id: int, *, tenant_id: int) -> list[dict[str, Any]]:
        db = get_session()
        try:
            q = (
                db.query(UnitDietAssignment, DietaryType)
                .join(Unit, Unit.id == UnitDietAssignment.unit_id)
                .join(DietaryType, DietaryType.id == UnitDietAssignment.dietary_type_id)
                .filter(
                    UnitDietAssignment.unit_id == unit_id,
                    Unit.tenant_id == tenant_id,
                    DietaryType.tenant_id == tenant_id,
                )
            )
            out = []
            for a, d in q.all():
                out.append(
                    {
                        "assignment_id": a.id,
                        "diet_type_id": d.id,
                        "diet_name": d.name,
                        "count": a.count,
                    }
                )
            return out
        finally:
            db.close()

    def set_assignment(
        self, unit_id: int, diet_type_id: int, count: int, *, tenant_id: int
    ) -> int:
        db = get_session()
        try:
            unit = db.query(Unit).filter_by(id=unit_id, tenant_id=tenant_id).first()
            diet_type = db.query(DietaryType).filter_by(
                id=diet_type_id, tenant_id=tenant_id
            ).first()
            if unit is None or diet_type is None:
                raise DietaryReferenceError("assignment_target_outside_tenant", 403)
            row: UnitDietAssignment | None = (
                db.query(UnitDietAssignment)
                .filter_by(unit_id=unit_id, dietary_type_id=diet_type_id)
                .first()
            )
            if row is not None:
                row.count = count
            else:
                row = UnitDietAssignment(unit_id=unit_id, dietary_type_id=diet_type_id, count=count)
                db.add(row)
            db.commit()
            assert row is not None  # for mypy: row always initialized
            return row.id
        finally:
            db.close()

    # --- Dietary Types CRUD ---
    def list_diet_types(self, tenant_id: int, *, site_id: str) -> list[dict[str, Any]]:
        db = get_session()
        try:
            scoped_site_id = self._require_site_scope(db, tenant_id, site_id)
            rows = (
                db.query(DietaryType)
                .filter_by(tenant_id=tenant_id, site_id=scoped_site_id)
                .order_by(DietaryType.id)
                .all()
            )
            return [{"id": r.id, "name": r.name, "default_select": r.default_select} for r in rows]
        finally:
            db.close()

    def create_diet_type(
        self,
        tenant_id: int,
        name: str,
        default_select: bool = False,
        *,
        site_id: str,
    ) -> int:
        db = get_session()
        try:
            scoped_site_id = self._require_site_scope(db, tenant_id, site_id)
            dt = DietaryType(
                tenant_id=tenant_id,
                site_id=scoped_site_id,
                name=name.strip(),
                diet_family=DIET_FAMILY_OTHER,
                default_select=default_select,
                semantics="legacy_bucket",
            )
            db.add(dt)
            db.flush()
            dt.requirement_key = f"legacy_{dt.id}"
            db.commit()
            db.refresh(dt)
            return dt.id
        finally:
            db.close()

    def update_diet_type(
        self,
        tenant_id: int,
        diet_type_id: int,
        name: str | None = None,
        default_select: bool | None = None,
        *,
        site_id: str,
    ) -> bool:
        db = get_session()
        try:
            scoped_site_id = self._require_site_scope(db, tenant_id, site_id)
            row = (
                db.query(DietaryType)
                .filter_by(
                    tenant_id=tenant_id,
                    site_id=scoped_site_id,
                    id=diet_type_id,
                )
                .first()
            )
            if not row:
                return False
            if name is not None:
                row.name = name.strip()
            if default_select is not None:
                row.default_select = default_select
            db.commit()
            return True
        finally:
            db.close()

    def delete_diet_type(
        self, tenant_id: int, diet_type_id: int, *, site_id: str
    ) -> bool:
        db = get_session()
        try:
            scoped_site_id = self._require_site_scope(db, tenant_id, site_id)
            row = (
                db.query(DietaryType)
                .filter_by(
                    tenant_id=tenant_id,
                    site_id=scoped_site_id,
                    id=diet_type_id,
                )
                .first()
            )
            if not row:
                return False
            if (
                db.query(UnitDietAssignment.id)
                .filter_by(dietary_type_id=diet_type_id)
                .first()
                is not None
            ):
                raise DietaryReferenceError("diet_type_has_legacy_assignments", 409)
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()

    def list_units(self, tenant_id: int) -> list[dict[str, Any]]:
        db = get_session()
        try:
            rows = db.query(Unit).filter_by(tenant_id=tenant_id).all()
            return [
                {"id": u.id, "name": u.name, "default_attendance": u.default_attendance}
                for u in rows
            ]
        finally:
            db.close()

    def delete_assignment(self, assignment_id: int, *, tenant_id: int) -> bool:
        db = get_session()
        try:
            row = (
                db.query(UnitDietAssignment)
                .join(Unit, Unit.id == UnitDietAssignment.unit_id)
                .join(DietaryType, DietaryType.id == UnitDietAssignment.dietary_type_id)
                .filter(
                    UnitDietAssignment.id == assignment_id,
                    Unit.tenant_id == tenant_id,
                    DietaryType.tenant_id == tenant_id,
                )
                .first()
            )
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()
