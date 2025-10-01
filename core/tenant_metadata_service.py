from __future__ import annotations

from typing import Any

from .db import get_session
from .models import TenantMetadata


class TenantMetadataService:
    def get(self, tenant_id: int) -> dict[str, Any] | None:
        db = get_session()
        try:
            row = db.query(TenantMetadata).filter_by(tenant_id=tenant_id).first()
            if not row:
                return None
            return {"tenant_id": tenant_id, "kind": row.kind, "description": row.description}
        finally:
            db.close()

    def upsert(self, tenant_id: int, kind: str | None, description: str | None) -> None:
        db = get_session()
        try:
            row = db.query(TenantMetadata).filter_by(tenant_id=tenant_id).first()
            if row:
                if kind is not None:
                    row.kind = kind
                if description is not None:
                    row.description = description
            else:
                row = TenantMetadata(tenant_id=tenant_id, kind=kind, description=description)
                db.add(row)
            db.commit()
        finally:
            db.close()
