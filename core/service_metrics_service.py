from __future__ import annotations

from datetime import date
from typing import Any, TypedDict, Optional, Dict, List, cast

from sqlalchemy import and_, func

from .db import get_session
from .models import ServiceMetric


class IngestRow(TypedDict, total=False):
    # Raw inbound row (all optional prior to validation)
    unit_id: int
    date: str
    meal: str
    dish_id: int | None
    category: str | None
    guest_count: int | None
    produced_qty_kg: float | None
    served_qty_kg: float | None
    leftover_qty_kg: float | None
    served_g_per_guest: float | None


class IngestResult(TypedDict):
    ok: bool
    inserted: int
    updated: int
    errors: List[str]


class MetricRow(TypedDict):
    date: str
    unit_id: int
    meal: str
    dish_id: int | None
    category: str | None
    guest_count: int | None
    produced_qty_kg: float | None
    served_qty_kg: float | None
    leftover_qty_kg: float | None
    served_g_per_guest: float | None


class SummaryDayRow(TypedDict):
    date: str
    unit_id: int
    meal: str
    guest_count: int
    produced_qty_kg: float
    served_qty_kg: float
    leftover_qty_kg: float
    served_g_per_guest: float | None


class ServiceMetricsService:
    def ingest(self, tenant_id: int, rows: list[IngestRow]) -> IngestResult:
        db = get_session()
        inserted = 0
        updated = 0
        errors: list[str] = []
        try:
            for r in rows:
                try:
                    norm = self._normalize_row(r)
                except ValueError as e:
                    errors.append(str(e))
                    continue
                norm["tenant_id"] = tenant_id
                key_filter = and_(
                    ServiceMetric.tenant_id == tenant_id,
                    ServiceMetric.unit_id == norm["unit_id"],
                    ServiceMetric.date == norm["date"],
                    ServiceMetric.meal == norm["meal"],
                    ServiceMetric.dish_id.is_(norm["dish_id"]) if norm["dish_id"] is None else ServiceMetric.dish_id == norm["dish_id"],
                    ServiceMetric.category == norm["category"]
                )
                existing = db.query(ServiceMetric).filter(key_filter).first()
                if existing:
                    updated += 1
                    for f in ["guest_count","produced_qty_kg","served_qty_kg","leftover_qty_kg","served_g_per_guest"]:
                        setattr(existing, f, norm.get(f))
                else:
                    sm = ServiceMetric(**norm)
                    db.add(sm)
                    inserted += 1
            db.commit()
            return {"ok": True, "inserted": inserted, "updated": updated, "errors": errors}
        finally:
            db.close()

    def query(self, tenant_id: int, filters: dict[str, Any]) -> list[MetricRow]:
        db = get_session()
        try:
            q = db.query(ServiceMetric).filter(ServiceMetric.tenant_id == tenant_id)
            if "unit_ids" in filters:
                q = q.filter(ServiceMetric.unit_id.in_(filters["unit_ids"]))
            if "date_from" in filters:
                q = q.filter(ServiceMetric.date >= self._parse_date(filters["date_from"]))
            if "date_to" in filters:
                q = q.filter(ServiceMetric.date <= self._parse_date(filters["date_to"]))
            if "meal" in filters:
                q = q.filter(ServiceMetric.meal == filters["meal"])
            if "category" in filters:
                q = q.filter(ServiceMetric.category == filters["category"])
            rows = q.all()
            return [self._row_dict(r) for r in rows]
        finally:
            db.close()

    def summary_day(self, tenant_id: int, date_from: date, date_to: date) -> list[SummaryDayRow]:
        db = get_session()
        try:
            q = db.query(
                ServiceMetric.date.label("d"),
                ServiceMetric.unit_id,
                ServiceMetric.meal,
                func.sum(ServiceMetric.guest_count).label("guest_count"),
                func.sum(ServiceMetric.produced_qty_kg).label("produced_qty_kg"),
                func.sum(ServiceMetric.served_qty_kg).label("served_qty_kg"),
                func.sum(ServiceMetric.leftover_qty_kg).label("leftover_qty_kg")
            ).filter(ServiceMetric.tenant_id == tenant_id, ServiceMetric.date >= date_from, ServiceMetric.date <= date_to)
            q = q.group_by(ServiceMetric.date, ServiceMetric.unit_id, ServiceMetric.meal)
            out: list[SummaryDayRow] = []
            for row in q.all():
                served_g_per_guest = None
                if row.guest_count and row.served_qty_kg:
                    served_g_per_guest = (row.served_qty_kg * 1000.0) / row.guest_count
                out.append({  # type: ignore[arg-type]
                    "date": row.d.isoformat(),
                    "unit_id": row.unit_id,
                    "meal": row.meal,
                    "guest_count": int(row.guest_count or 0),
                    "produced_qty_kg": float(row.produced_qty_kg or 0),
                    "served_qty_kg": float(row.served_qty_kg or 0),
                    "leftover_qty_kg": float(row.leftover_qty_kg or 0),
                    "served_g_per_guest": served_g_per_guest
                })
            return out
        finally:
            db.close()

    # --- Helpers ---
    def _normalize_row(self, r: IngestRow) -> dict[str, Any]:  # validated normalized dict with concrete python types
        required = ["unit_id","date","meal"]
        for f in required:
            if f not in r:
                raise ValueError(f"missing field {f}")
        if "date" not in r:
            raise ValueError("missing field date")
        try:
            d = self._parse_date(r["date"])
        except Exception:
            # Hide underlying parsing details for a consistent public error
            raise ValueError("invalid date") from None
        if "meal" not in r:
            raise ValueError("missing field meal")
        meal = r["meal"]
        if meal not in {"lunch","dinner","evening"}:
            raise ValueError("invalid meal")
        dish_id = r.get("dish_id")
        category = r.get("category")
        if dish_id is None and not category:
            raise ValueError("dish_id or category required")
        guest_count = r.get("guest_count")
        produced = cast(float | int | None, r.get("produced_qty_kg"))
        served = cast(float | int | None, r.get("served_qty_kg"))
        leftover = cast(float | int | None, r.get("leftover_qty_kg"))
        for num_field in ["guest_count","produced_qty_kg","served_qty_kg","leftover_qty_kg"]:
            v_any = r.get(num_field)
            if isinstance(v_any, (int, float)) and v_any < 0:
                raise ValueError(f"{num_field} negative")
        if isinstance(produced, (int, float)) and isinstance(served, (int, float)) and served > produced:
            raise ValueError("served > produced")
        if isinstance(produced, (int, float)) and isinstance(leftover, (int, float)) and leftover > produced:
            raise ValueError("leftover > produced")
        served_g_per_guest = r.get("served_g_per_guest")
        if served_g_per_guest is None and isinstance(guest_count, int) and isinstance(served, (int, float)):
            served_g_per_guest = (served * 1000.0) / guest_count if guest_count > 0 else None
        if "unit_id" not in r:
            raise ValueError("missing field unit_id")
        return {
            "unit_id": r["unit_id"],
            "date": d,  # date object (model expects date)
            "meal": meal,
            "dish_id": dish_id,
            "category": category,
            "guest_count": guest_count,
            "produced_qty_kg": produced,
            "served_qty_kg": served,
            "leftover_qty_kg": leftover,
            "served_g_per_guest": served_g_per_guest
        }

    def _parse_date(self, s: str) -> date:
        return date.fromisoformat(s)

    def _row_dict(self, m: ServiceMetric) -> MetricRow:
        return {
            "date": m.date.isoformat(),
            "unit_id": m.unit_id,
            "meal": m.meal,
            "dish_id": m.dish_id,
            "category": m.category,
            "guest_count": m.guest_count,
            "produced_qty_kg": m.produced_qty_kg,
            "served_qty_kg": m.served_qty_kg,
            "leftover_qty_kg": m.leftover_qty_kg,
            "served_g_per_guest": m.served_g_per_guest,
        }
