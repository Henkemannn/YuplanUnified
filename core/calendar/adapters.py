from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from modules.offshore2.menu_context import _service as _menu_context_service
from modules.offshore2.models import OffshoreServiceEvent, OffshoreWorkPeriod
from modules.offshore2.permissions import VIEWER_ROLES

from ..db import get_session
from .contracts import CalendarItemMetadata, CalendarItemRead, CalendarUserContext


@dataclass(slots=True)
class OffshoreCalendarAdapter:
    adapter_name: str = "offshore"

    def _can_read(self, user_context: CalendarUserContext) -> bool:
        role = (user_context.role or "").strip().lower()
        return role in VIEWER_ROLES

    def _can_edit(self, user_context: CalendarUserContext) -> bool:
        role = (user_context.role or "").strip().lower()
        return role in {"editor", "admin", "superuser"}

    def _detail_url(self, period_id: int) -> str:
        return f"/offshore/periods/{int(period_id)}"

    def get_items(
        self,
        *,
        tenant_id: int,
        site_id: str | None,
        range_start: datetime,
        range_end: datetime,
        user_context: CalendarUserContext,
    ) -> list[CalendarItemRead]:
        if not self._can_read(user_context):
            return []
        if site_id is None or not str(site_id).strip():
            return []

        db = get_session()
        try:
            events = (
                db.query(OffshoreServiceEvent)
                .filter(
                    OffshoreServiceEvent.tenant_id == int(tenant_id),
                    OffshoreServiceEvent.site_id == str(site_id),
                    OffshoreServiceEvent.starts_at >= range_start,
                    OffshoreServiceEvent.starts_at < range_end,
                )
                .order_by(OffshoreServiceEvent.starts_at.asc(), OffshoreServiceEvent.id.asc())
                .all()
            )
            period_ids = [int(event.work_period_id) for event in events]
            periods_by_id: dict[int, OffshoreWorkPeriod] = {}
            if period_ids:
                periods = (
                    db.query(OffshoreWorkPeriod)
                    .filter(
                        OffshoreWorkPeriod.tenant_id == int(tenant_id),
                        OffshoreWorkPeriod.site_id == str(site_id),
                        OffshoreWorkPeriod.id.in_(period_ids),
                    )
                    .all()
                )
                periods_by_id = {int(period.id): period for period in periods}
        finally:
            db.close()

        contexts_by_event_id: dict[int, object] = {}
        for period_id in sorted(set(period_ids)):
            try:
                for context in _menu_context_service.list_contexts_for_period(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id),
                    work_period_id=int(period_id),
                ):
                    contexts_by_event_id[int(context.service_event_id)] = context
            except Exception:
                continue

        items: list[CalendarItemRead] = []
        for event in events:
            period = periods_by_id.get(int(event.work_period_id))
            context = contexts_by_event_id.get(int(event.id))
            starts_at = event.starts_at
            if starts_at.tzinfo is None or starts_at.utcoffset() is None:
                starts_at = starts_at.replace(tzinfo=UTC)
            item = CalendarItemRead(
                source_module="offshore",
                source_type="service_event",
                source_id=str(event.id),
                tenant_id=int(event.tenant_id),
                site_id=str(event.site_id),
                starts_at=starts_at,
                ends_at=None,
                all_day=False,
                title=str(event.display_name),
                category="service_event",
                status=str(event.status),
                detail_url=self._detail_url(int(event.work_period_id)),
                editable=self._can_edit(user_context),
                priority=None,
                audience=None,
                visibility="site",
                related_entity_type="work_period",
                related_entity_id=int(period.id) if period is not None else int(event.work_period_id),
                metadata=CalendarItemMetadata(
                    menu_context_status=(str(getattr(context, "resolution_status", "")).strip() or None)
                ),
            )
            items.append(item)
        return items
