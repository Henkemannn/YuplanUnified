from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .db import get_session
from .models import ShiftSlot, ShiftTemplate

ISO_FMT = "%Y-%m-%dT%H:%M:%S"


def parse_ts(val: str) -> datetime:
    # Accept with or without seconds
    try:
        if len(val) == 16:  # YYYY-MM-DDTHH:MM
            val = val + ":00"
        return datetime.fromisoformat(val)
    except Exception:
        # Suppress original stack to make validation error cleaner
        raise ValueError("invalid datetime format") from None


class TurnusService:
    def get_templates(self, tenant_id: int) -> list[dict[str, Any]]:
        db = get_session()
        try:
            rows = (
                db.query(ShiftTemplate)
                .filter_by(tenant_id=tenant_id)
                .order_by(ShiftTemplate.id)
                .all()
            )
            return [{"id": r.id, "name": r.name, "pattern_type": r.pattern_type} for r in rows]
        finally:
            db.close()

    def create_template(self, tenant_id: int, name: str, pattern_type: str) -> int:
        db = get_session()
        try:
            existing: ShiftTemplate | None = (
                db.query(ShiftTemplate).filter_by(tenant_id=tenant_id, name=name).first()
            )
            if existing is not None:
                return int(existing.id)
            tpl = ShiftTemplate(tenant_id=tenant_id, name=name, pattern_type=pattern_type)
            db.add(tpl)
            db.commit()
            db.refresh(tpl)
            return int(tpl.id)
        finally:
            db.close()

    def import_shifts(
        self, tenant_id: int, template_id: int, shifts: list[dict[str, Any]]
    ) -> dict[str, int]:
        db = get_session()
        inserted = 0
        skipped = 0
        try:
            seen = set()  # track duplicates inside same batch (unit_id,start_ts,end_ts,role)
            for s in shifts:
                try:
                    start_ts = parse_ts(s["start_ts"])
                    end_ts = parse_ts(s["end_ts"])
                except Exception:
                    skipped += 1
                    continue
                if end_ts <= start_ts:
                    skipped += 1
                    continue
                unit_id = s.get("unit_id")
                role = (s.get("role") or "").strip() or None
                key = (unit_id, start_ts, end_ts, role)
                if key in seen:
                    skipped += 1
                    continue
                # duplicate check
                exists = (
                    db.query(ShiftSlot)
                    .filter_by(
                        tenant_id=tenant_id,
                        unit_id=unit_id,
                        start_ts=start_ts,
                        end_ts=end_ts,
                        role=role,
                    )
                    .first()
                )
                if exists:
                    skipped += 1
                    continue
                slot = ShiftSlot(
                    tenant_id=tenant_id,
                    unit_id=unit_id,
                    template_id=template_id,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    role=role,
                    status="planned",
                    notes=None,
                )
                db.add(slot)
                seen.add(key)
                inserted += 1
            db.commit()
            return {"inserted": inserted, "skipped": skipped}
        finally:
            db.close()

    def query_slots(
        self,
        tenant_id: int,
        date_from: date,
        date_to: date,
        unit_ids: list[int] | None = None,
        role: str | None = None,
    ) -> list[dict[str, Any]]:
        db = get_session()
        try:
            q = db.query(ShiftSlot).filter(
                ShiftSlot.tenant_id == tenant_id,
                ShiftSlot.start_ts >= datetime.combine(date_from, datetime.min.time()),
                ShiftSlot.start_ts <= datetime.combine(date_to, datetime.max.time()),
            )
            if unit_ids:
                q = q.filter(ShiftSlot.unit_id.in_(unit_ids))
            if role:
                q = q.filter(ShiftSlot.role == role)
            out = []
            for r in q.order_by(ShiftSlot.start_ts).all():
                out.append(
                    {
                        "id": r.id,
                        "unit_id": r.unit_id,
                        "template_id": r.template_id,
                        "start_ts": r.start_ts.isoformat(timespec="seconds"),
                        "end_ts": r.end_ts.isoformat(timespec="seconds"),
                        "role": r.role,
                        "status": r.status,
                    }
                )
            return out
        finally:
            db.close()
