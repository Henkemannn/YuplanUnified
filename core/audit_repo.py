"""Audit repository: persistence + query + retention (strict pocket)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import String, and_, cast, delete, func, select

from .db import get_session
from .models import AuditEvent


class AuditQueryFilters:
    def __init__(
        self,
        tenant_id: int | None = None,
        event: str | None = None,
        ts_from: datetime | None = None,
        ts_to: datetime | None = None,
        text: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.event = event
        self.ts_from = ts_from
        self.ts_to = ts_to
        self.text = text


class AuditRepo:
    def insert(
        self,
        *,
        event: str,
        tenant_id: int | None,
        actor_user_id: int | None,
        actor_role: str | None,
        payload: dict | None,
        request_id: str | None,
    ) -> None:
        db = get_session()
        try:
            db.add(
                AuditEvent(
                    event=event,
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    actor_role=actor_role,
                    payload=payload,
                    request_id=request_id,
                )
            )
            db.commit()
        finally:
            db.close()

    def query(
        self, filters: AuditQueryFilters, page: int, size: int
    ) -> tuple[list[AuditEvent], int]:
        db = get_session()
        try:
            stmt = select(AuditEvent)
            conds = []
            if filters.tenant_id is not None:
                conds.append(AuditEvent.tenant_id == filters.tenant_id)
            if filters.event:
                conds.append(AuditEvent.event == filters.event)
            if filters.ts_from:
                conds.append(AuditEvent.ts >= filters.ts_from)
            if filters.ts_to:
                conds.append(AuditEvent.ts <= filters.ts_to)
            if filters.text:
                # simple JSON string search fallback (cast JSON -> TEXT then ILIKE)
                conds.append(cast(AuditEvent.payload, String).ilike(f"%{filters.text}%"))
            if conds:
                stmt = stmt.where(and_(*conds))
            stmt = stmt.order_by(AuditEvent.ts.desc())
            total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
            offset = (page - 1) * size
            rows = list(db.execute(stmt.limit(size).offset(offset)).scalars().all())
            return rows, int(total)
        finally:
            db.close()

    def purge_older_than(self, days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        db = get_session()
        try:
            stmt = delete(AuditEvent).where(AuditEvent.ts < cutoff)
            res = db.execute(stmt)
            db.commit()
            return res.rowcount or 0
        finally:
            db.close()


__all__ = ["AuditRepo", "AuditQueryFilters"]
