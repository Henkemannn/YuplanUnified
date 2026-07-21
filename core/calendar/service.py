from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .contracts import (
    CalendarFeedResult,
    CalendarFeedWarning,
    CalendarItemRead,
    CalendarReadAdapter,
    CalendarUserContext,
)


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _overlaps_range(item: CalendarItemRead, range_start: datetime, range_end: datetime) -> bool:
    if item.starts_at >= range_end:
        return False
    if item.ends_at is None:
        return item.starts_at < range_end and item.starts_at >= range_start
    return item.starts_at < range_end and item.ends_at > range_start


@dataclass(slots=True)
class CalendarFeedService:
    adapters: list[CalendarReadAdapter] = field(default_factory=list)
    default_range_days: int = 14
    max_range_days: int = 92

    def register_adapter(self, adapter: CalendarReadAdapter) -> None:
        self.adapters.append(adapter)

    def get_feed(
        self,
        *,
        tenant_id: int,
        site_id: str | None,
        range_start: datetime,
        range_end: datetime,
        user_context: CalendarUserContext,
    ) -> CalendarFeedResult:
        if not _is_timezone_aware(range_start):
            raise ValueError("range_start must be timezone-aware")
        if not _is_timezone_aware(range_end):
            raise ValueError("range_end must be timezone-aware")
        if range_end <= range_start:
            raise ValueError("range_end must be after range_start")
        if (range_end - range_start) > timedelta(days=int(self.max_range_days)):
            raise ValueError("range exceeds maximum window")

        items_by_identity: dict[tuple[str, str, str], CalendarItemRead] = {}
        warnings: list[CalendarFeedWarning] = []

        for adapter in list(self.adapters):
            adapter_name = str(getattr(adapter, "adapter_name", adapter.__class__.__name__))
            try:
                adapter_items = adapter.get_items(
                    tenant_id=int(tenant_id),
                    site_id=site_id,
                    range_start=range_start,
                    range_end=range_end,
                    user_context=user_context,
                )
            except Exception as exc:
                warnings.append(
                    CalendarFeedWarning(
                        adapter_name=adapter_name,
                        code="adapter_error",
                        message=str(exc) or "adapter_error",
                    )
                )
                continue

            for item in adapter_items:
                if int(item.tenant_id) != int(tenant_id):
                    continue
                if site_id is None:
                    if item.site_id is not None:
                        continue
                elif item.site_id is not None and str(item.site_id) != str(site_id):
                    continue
                if not _overlaps_range(item, range_start, range_end):
                    continue

                identity = item.identity
                existing = items_by_identity.get(identity)
                if existing is None:
                    items_by_identity[identity] = item
                    continue
                if existing.to_dict() != item.to_dict():
                    warnings.append(
                        CalendarFeedWarning(
                            adapter_name=adapter_name,
                            code="duplicate_identity",
                            message="duplicate source identity",
                            identity=identity,
                        )
                    )

        items = sorted(
            items_by_identity.values(),
            key=lambda item: (
                item.starts_at,
                str(item.category or ""),
                str(item.title or ""),
                str(item.source_module or ""),
                str(item.source_type or ""),
                str(item.source_id or ""),
            ),
        )
        return CalendarFeedResult(
            items=items,
            warnings=warnings,
            range_start=range_start,
            range_end=range_end,
        )
