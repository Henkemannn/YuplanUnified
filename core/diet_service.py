from __future__ import annotations

from typing import Any

from .db import get_session
from .models import DietaryType, Unit, UnitDietAssignment


class DietService:
    def __init__(self):
        pass

    def list_assignments(self, unit_id: int) -> list[dict[str, Any]]:
        db = get_session()
        try:
            q = db.query(UnitDietAssignment, DietaryType).join(DietaryType, DietaryType.id == UnitDietAssignment.dietary_type_id).filter(UnitDietAssignment.unit_id == unit_id)
            out = []
            for a, d in q.all():
                out.append({"assignment_id": a.id, "diet_type_id": d.id, "diet_name": d.name, "count": a.count})
            return out
        finally:
            db.close()

    def set_assignment(self, unit_id: int, diet_type_id: int, count: int) -> int:
        db = get_session()
        try:
            row: UnitDietAssignment | None = db.query(UnitDietAssignment).filter_by(unit_id=unit_id, dietary_type_id=diet_type_id).first()
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
    def list_diet_types(self, tenant_id: int) -> list[dict[str, Any]]:
        db = get_session()
        try:
            rows = db.query(DietaryType).filter_by(tenant_id=tenant_id).order_by(DietaryType.id).all()
            return [
                {"id": r.id, "name": r.name, "default_select": r.default_select}
                for r in rows
            ]
        finally:
            db.close()

    def create_diet_type(self, tenant_id: int, name: str, default_select: bool=False) -> int:
        db = get_session()
        try:
            dt = DietaryType(tenant_id=tenant_id, name=name.strip(), default_select=default_select)
            db.add(dt)
            db.commit()
            db.refresh(dt)
            return dt.id
        finally:
            db.close()

    def update_diet_type(self, tenant_id: int, diet_type_id: int, name: str | None=None, default_select: bool | None=None) -> bool:
        db = get_session()
        try:
            row = db.query(DietaryType).filter_by(tenant_id=tenant_id, id=diet_type_id).first()
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

    def delete_diet_type(self, tenant_id: int, diet_type_id: int) -> bool:
        db = get_session()
        try:
            row = db.query(DietaryType).filter_by(tenant_id=tenant_id, id=diet_type_id).first()
            if not row:
                return False
            # Also delete assignments referencing it
            db.query(UnitDietAssignment).filter_by(dietary_type_id=diet_type_id).delete()
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()

    def list_units(self, tenant_id: int) -> list[dict[str, Any]]:
        db = get_session()
        try:
            rows = db.query(Unit).filter_by(tenant_id=tenant_id).all()
            return [{"id": u.id, "name": u.name, "default_attendance": u.default_attendance} for u in rows]
        finally:
            db.close()

    def delete_assignment(self, assignment_id: int) -> bool:
        db = get_session()
        try:
            row = db.query(UnitDietAssignment).filter_by(id=assignment_id).first()
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()
