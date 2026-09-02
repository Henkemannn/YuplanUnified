from __future__ import annotations

from datetime import UTC, datetime
import uuid
from typing import Iterable

from .db import get_session
from .models import (
    Department,
    DepartmentRequirementGroup,
    DepartmentRequirementGroupRequirement,
    DietaryType,
)


class DepartmentRequirementGroupsRepo:
    def _ensure_table(self, db) -> None:
        bind = getattr(db, "bind", None)
        if bind is None or getattr(getattr(bind, "dialect", None), "name", "") != "sqlite":
            return
        DepartmentRequirementGroup.__table__.create(bind=bind, checkfirst=True)
        DepartmentRequirementGroupRequirement.__table__.create(bind=bind, checkfirst=True)

    def _normalize_default_quantity(self, default_quantity: int | str | None) -> int:
        quantity = int(default_quantity or 0)
        if quantity < 0:
            raise ValueError("default_quantity_negative")
        return quantity

    def _normalize_label(self, label: str | None) -> str | None:
        clean = str(label or "").strip()
        return clean or None

    def _normalize_requirement_ids(self, requirement_ids: Iterable[int | str]) -> list[int]:
        normalized: list[int] = []
        seen: set[int] = set()
        for raw in requirement_ids:
            value = int(str(raw).strip())
            if value in seen:
                raise ValueError("duplicate_requirement_id")
            seen.add(value)
            normalized.append(value)
        if not normalized:
            raise ValueError("requirements_required")
        return sorted(normalized)

    def _load_department_site_id(self, db, department_id: str) -> str:
        department = db.get(Department, str(department_id))
        if department is None:
            raise ValueError("department_not_found")
        site_id = str(department.site_id or "").strip()
        if not site_id:
            raise ValueError("department_site_missing")
        return site_id

    def _load_atomic_requirement(self, db, dietary_type_id: int, department_site_id: str) -> DietaryType:
        requirement = db.get(DietaryType, int(dietary_type_id))
        if requirement is None:
            raise ValueError("dietary_type_not_found")
        requirement_key = str(requirement.requirement_key or "").strip()
        if not requirement_key:
            raise ValueError("dietary_type_requirement_key_missing")
        requirement_site_id = str(requirement.site_id or "").strip()
        if not requirement_site_id:
            raise ValueError("dietary_type_site_missing")
        if requirement_site_id != department_site_id:
            raise ValueError("dietary_type_site_mismatch")
        if str(requirement.semantics or "").strip().lower() != "atomic":
            raise ValueError("dietary_type_not_atomic")
        return requirement

    def _serialize_group(self, db, group: DepartmentRequirementGroup) -> dict:
        requirement_rows = (
            db.query(DietaryType)
            .join(
                DepartmentRequirementGroupRequirement,
                DietaryType.id == DepartmentRequirementGroupRequirement.dietary_type_id,
            )
            .filter(DepartmentRequirementGroupRequirement.group_id == group.id)
            .order_by(DietaryType.requirement_key.asc(), DietaryType.id.asc())
            .all()
        )
        return {
            "id": str(group.id),
            "department_id": str(group.department_id),
            "label": str(group.label) if group.label is not None else None,
            "default_quantity": int(group.default_quantity or 0),
            "is_active": bool(group.is_active),
            "requirements": [
                {
                    "dietary_type_id": int(requirement.id),
                    "requirement_key": str(requirement.requirement_key) if requirement.requirement_key is not None else None,
                    "name": str(requirement.name),
                    "semantics": str(requirement.semantics) if requirement.semantics is not None else None,
                }
                for requirement in requirement_rows
            ],
        }

    def create_group(
        self,
        department_id: str,
        default_quantity: int | str | None,
        requirement_ids: Iterable[int | str],
        label: str | None = None,
    ) -> dict:
        db = get_session()
        try:
            self._ensure_table(db)
            department_site_id = self._load_department_site_id(db, department_id)
            quantity = self._normalize_default_quantity(default_quantity)
            clean_label = self._normalize_label(label)
            normalized_requirement_ids = self._normalize_requirement_ids(requirement_ids)
            requirements = [
                self._load_atomic_requirement(db, dietary_type_id, department_site_id)
                for dietary_type_id in normalized_requirement_ids
            ]
            group = DepartmentRequirementGroup(
                id=str(uuid.uuid4()),
                department_id=str(department_id),
                label=clean_label,
                default_quantity=quantity,
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(group)
            for requirement in requirements:
                db.add(
                    DepartmentRequirementGroupRequirement(
                        group_id=group.id,
                        dietary_type_id=int(requirement.id),
                    )
                )
            db.commit()
            return self.get_group(group.id) or self._serialize_group(db, group)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_group(self, group_id: str) -> dict | None:
        db = get_session()
        try:
            self._ensure_table(db)
            group = db.get(DepartmentRequirementGroup, str(group_id))
            if group is None:
                return None
            return self._serialize_group(db, group)
        finally:
            db.close()

    def list_for_department(self, department_id: str) -> list[dict]:
        db = get_session()
        try:
            self._ensure_table(db)
            groups = (
                db.query(DepartmentRequirementGroup)
                .filter(DepartmentRequirementGroup.department_id == str(department_id))
                .order_by(DepartmentRequirementGroup.is_active.desc(), DepartmentRequirementGroup.id.asc())
                .all()
            )
            return [self._serialize_group(db, group) for group in groups]
        finally:
            db.close()

    def update_group(
        self,
        group_id: str,
        label: str | None = None,
        default_quantity: int | str | None = None,
        is_active: bool | None = None,
    ) -> dict | None:
        db = get_session()
        try:
            self._ensure_table(db)
            group = db.get(DepartmentRequirementGroup, str(group_id))
            if group is None:
                return None
            if label is not None:
                group.label = self._normalize_label(label)
            if default_quantity is not None:
                group.default_quantity = self._normalize_default_quantity(default_quantity)
            if is_active is not None:
                group.is_active = bool(is_active)
            group.updated_at = datetime.now(UTC)
            db.commit()
            return self.get_group(group.id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def replace_requirements(self, group_id: str, requirement_ids: Iterable[int | str]) -> dict | None:
        db = get_session()
        try:
            self._ensure_table(db)
            group = db.get(DepartmentRequirementGroup, str(group_id))
            if group is None:
                return None
            department_site_id = self._load_department_site_id(db, group.department_id)
            normalized_requirement_ids = self._normalize_requirement_ids(requirement_ids)
            requirements = [
                self._load_atomic_requirement(db, dietary_type_id, department_site_id)
                for dietary_type_id in normalized_requirement_ids
            ]
            db.query(DepartmentRequirementGroupRequirement).filter(
                DepartmentRequirementGroupRequirement.group_id == group.id
            ).delete(synchronize_session=False)
            for requirement in requirements:
                db.add(
                    DepartmentRequirementGroupRequirement(
                        group_id=group.id,
                        dietary_type_id=int(requirement.id),
                    )
                )
            group.updated_at = datetime.now(UTC)
            db.commit()
            return self.get_group(group.id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def deactivate_group(self, group_id: str) -> dict | None:
        return self.update_group(group_id, is_active=False)


__all__ = ["DepartmentRequirementGroupsRepo"]
