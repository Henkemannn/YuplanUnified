from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

ALLOWED_PRIORITIES = {"low", "normal", "high", "critical"}
ALLOWED_VISIBILITIES = {"private", "site", "tenant", "department", "role", "public"}


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True, slots=True)
class CalendarUserContext:
    tenant_id: int | None
    site_id: str | None
    user_id: int | None = None
    role: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class CalendarItemMetadata:
    menu_context_status: str | None = None


@dataclass(frozen=True, slots=True)
class CalendarItemRead:
    source_module: str
    source_type: str
    source_id: str
    tenant_id: int
    site_id: str | None
    starts_at: datetime
    ends_at: datetime | None
    all_day: bool
    title: str
    category: str
    status: str
    detail_url: str | None
    editable: bool
    priority: str | None = None
    audience: str | None = None
    visibility: str | None = None
    related_entity_type: str | None = None
    related_entity_id: str | int | None = None
    metadata: CalendarItemMetadata | None = None

    def __post_init__(self) -> None:
        if not str(self.source_module or "").strip():
            raise ValueError("source_module is required")
        if not str(self.source_type or "").strip():
            raise ValueError("source_type is required")
        if not str(self.source_id or "").strip():
            raise ValueError("source_id is required")
        if int(self.tenant_id) <= 0:
            raise ValueError("tenant_id must be positive")
        if self.site_id is not None and not str(self.site_id).strip():
            raise ValueError("site_id cannot be blank")
        if not _is_timezone_aware(self.starts_at):
            raise ValueError("starts_at must be timezone-aware")
        if self.ends_at is not None:
            if not _is_timezone_aware(self.ends_at):
                raise ValueError("ends_at must be timezone-aware")
            if self.ends_at <= self.starts_at:
                raise ValueError("ends_at must be after starts_at")
        if self.priority is not None and self.priority not in ALLOWED_PRIORITIES:
            raise ValueError("invalid priority")
        if self.visibility is not None and self.visibility not in ALLOWED_VISIBILITIES:
            raise ValueError("invalid visibility")
        if self.related_entity_type is None and self.related_entity_id is not None:
            raise ValueError("related_entity_type required when related_entity_id is set")
        if self.related_entity_type is not None and not str(self.related_entity_type).strip():
            raise ValueError("related_entity_type cannot be blank")
        if self.detail_url is not None and not str(self.detail_url).startswith("/"):
            raise ValueError("detail_url must be a safe internal path")

    @property
    def identity(self) -> tuple[str, str, str]:
        return (str(self.source_module), str(self.source_type), str(self.source_id))

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_module": self.source_module,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "tenant_id": self.tenant_id,
            "site_id": self.site_id,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat() if self.ends_at is not None else None,
            "all_day": self.all_day,
            "title": self.title,
            "category": self.category,
            "status": self.status,
            "detail_url": self.detail_url,
            "editable": self.editable,
            "priority": self.priority,
            "audience": self.audience,
            "visibility": self.visibility,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
        }
        if self.metadata is not None:
            payload["metadata"] = {"menu_context_status": self.metadata.menu_context_status}
        return payload


@dataclass(frozen=True, slots=True)
class CalendarFeedWarning:
    adapter_name: str
    code: str
    message: str
    identity: tuple[str, str, str] | None = None


@dataclass(frozen=True, slots=True)
class CalendarFeedResult:
    items: list[CalendarItemRead]
    warnings: list[CalendarFeedWarning]
    range_start: datetime
    range_end: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "items": [item.to_dict() for item in self.items],
            "warnings": [
                {
                    "adapter_name": warning.adapter_name,
                    "code": warning.code,
                    "message": warning.message,
                    "identity": list(warning.identity) if warning.identity is not None else None,
                }
                for warning in self.warnings
            ],
            "range_start": self.range_start.isoformat(),
            "range_end": self.range_end.isoformat(),
        }


class CalendarReadAdapter(Protocol):
    adapter_name: str

    def get_items(
        self,
        *,
        tenant_id: int,
        site_id: str | None,
        range_start: datetime,
        range_end: datetime,
        user_context: CalendarUserContext,
    ) -> list[CalendarItemRead]: ...
