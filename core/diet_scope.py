from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


WEEKVIEW_RESERVED_DIET_KEYS = frozenset({"normal", "normalkost"})


class DietaryReferenceError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _diet_id(value: object) -> int:
    raw = str(value).strip()
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 19:
        raise DietaryReferenceError("invalid_diet_type_id", 400)
    try:
        ident = int(raw)
    except ValueError as exc:
        raise DietaryReferenceError("invalid_diet_type_id", 400) from exc
    if raw != str(ident) or ident <= 0 or ident > 9223372036854775807:
        raise DietaryReferenceError("invalid_diet_type_id", 400)
    return ident


def _department_scope(db: Session, tenant_id: int | str, department_id: str) -> str:
    row = db.execute(
        text(
            "SELECT d.site_id, s.tenant_id FROM departments d "
            "JOIN sites s ON s.id=d.site_id WHERE d.id=:department"
        ),
        {"department": str(department_id)},
    ).first()
    if row is None or str(row[1]) != str(tenant_id):
        raise DietaryReferenceError("department_scope_mismatch", 403)
    return str(row[0])


def canonical_diet_id_for_site(
    db: Session,
    *,
    tenant_id: int | str,
    site_id: str,
    diet_type_id: object,
) -> int:
    ident = _diet_id(diet_type_id)
    site = db.execute(
        text("SELECT tenant_id FROM sites WHERE id=:site"),
        {"site": str(site_id)},
    ).first()
    if site is None or str(site[0]) != str(tenant_id):
        raise DietaryReferenceError("site_scope_mismatch", 403)
    diet = db.execute(
        text("SELECT tenant_id, site_id FROM dietary_types WHERE id=:diet"),
        {"diet": ident},
    ).first()
    if diet is None:
        raise DietaryReferenceError("unknown_diet_type_id", 400)
    if str(diet[0]) != str(tenant_id) or str(diet[1] or "") != str(site_id):
        raise DietaryReferenceError("diet_type_outside_scope", 403)
    return ident


def canonical_diet_id_for_department(
    db: Session,
    *,
    tenant_id: int | str,
    department_id: str,
    diet_type_id: object,
) -> int:
    site_id = _department_scope(db, tenant_id, department_id)
    return canonical_diet_id_for_site(
        db,
        tenant_id=tenant_id,
        site_id=site_id,
        diet_type_id=diet_type_id,
    )


def weekview_diet_key_for_department(
    db: Session,
    *,
    tenant_id: int | str,
    department_id: str,
    diet_type_id: object,
) -> str:
    site_id = _department_scope(db, tenant_id, department_id)
    raw = str(diet_type_id).strip()
    reserved = raw.casefold()
    if reserved in WEEKVIEW_RESERVED_DIET_KEYS:
        return reserved
    ident = canonical_diet_id_for_site(
        db,
        tenant_id=tenant_id,
        site_id=site_id,
        diet_type_id=raw,
    )
    return str(ident)
