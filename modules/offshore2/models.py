from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class OffshoreInstallationSettings(Base):
    __tablename__ = "offshore_installation_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Oslo", server_default="Europe/Oslo")
    default_locale: Mapped[str] = mapped_column(String(8), nullable=False, default="sv", server_default="sv")
    default_theme: Mapped[str] = mapped_column(String(16), nullable=False, default="system", server_default="system")
    default_portions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    menu_track_visibility_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "site_id", name="uq_offshore_installation_settings_tenant_site"),
        Index("ix_offshore_installation_settings_tenant_site", "tenant_id", "site_id"),
        CheckConstraint("length(trim(timezone)) > 0", name="ck_offshore_installation_settings_timezone_not_empty"),
        CheckConstraint("lower(default_locale) IN ('sv', 'no', 'en')", name="ck_offshore_installation_settings_locale_allowed"),
        CheckConstraint("lower(default_theme) IN ('system', 'light', 'dark')", name="ck_offshore_installation_settings_theme_allowed"),
        CheckConstraint("default_portions IS NULL OR default_portions BETWEEN 1 AND 10000", name="ck_offshore_installation_settings_default_portions_range"),
    )


class OffshoreWorkPosition(Base):
    __tablename__ = "offshore_work_positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "site_id", "code", name="uq_offshore_work_positions_tenant_site_code"),
        Index("ix_offshore_work_positions_tenant_site_sort", "tenant_id", "site_id", "sort_order"),
        Index("ix_offshore_work_positions_tenant_site_active", "tenant_id", "site_id", "is_active"),
        CheckConstraint("length(trim(code)) > 0", name="ck_offshore_work_positions_code_not_empty"),
        CheckConstraint("length(trim(name)) > 0", name="ck_offshore_work_positions_name_not_empty"),
        CheckConstraint("lower(position_type) IN ('cook', 'lead', 'bakery', 'other')", name="ck_offshore_work_positions_position_type_allowed"),
    )


class OffshoreMenuCycle(Base):
    __tablename__ = "offshore_menu_cycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cycle_length: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_offshore_menu_cycles_tenant_site_active", "tenant_id", "site_id", "is_active"),
        Index("ix_offshore_menu_cycles_tenant_site_name", "tenant_id", "site_id", "name"),
        CheckConstraint("length(trim(name)) > 0", name="ck_offshore_menu_cycles_name_not_empty"),
        CheckConstraint("cycle_length BETWEEN 1 AND 52", name="ck_offshore_menu_cycles_cycle_length_range"),
    )


class OffshoreMenuCycleSlot(Base):
    __tablename__ = "offshore_menu_cycle_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    menu_cycle_id: Mapped[int] = mapped_column(ForeignKey("offshore_menu_cycles.id", ondelete="CASCADE"), nullable=False)
    cycle_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint("menu_cycle_id", "cycle_index", name="uq_offshore_menu_cycle_slots_cycle_index"),
        Index("ix_offshore_menu_cycle_slots_cycle_sort", "menu_cycle_id", "sort_order"),
        Index("ix_offshore_menu_cycle_slots_tenant_site", "tenant_id", "site_id"),
        CheckConstraint("cycle_index >= 1", name="ck_offshore_menu_cycle_slots_cycle_index_positive"),
        CheckConstraint("length(trim(label)) > 0", name="ck_offshore_menu_cycle_slots_label_not_empty"),
    )


class OffshorePeriodTemplate(Base):
    __tablename__ = "offshore_period_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    start_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint("tenant_id", "site_id", "name", "active", name="uq_offshore_period_templates_tenant_site_name_active"),
        Index("ix_offshore_period_templates_tenant_site_active_sort", "tenant_id", "site_id", "active", "sort_order"),
        Index("ix_offshore_period_templates_tenant_site_name", "tenant_id", "site_id", "name"),
        CheckConstraint("length(trim(name)) > 0", name="ck_offshore_period_templates_name_not_empty"),
        CheckConstraint("duration_days >= 1", name="ck_offshore_period_templates_duration_positive"),
        CheckConstraint("start_weekday IS NULL OR start_weekday BETWEEN 0 AND 6", name="ck_offshore_period_templates_start_weekday_range"),
    )


class OffshorePeriodTemplateEvent(Base):
    __tablename__ = "offshore_period_template_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    period_template_id: Mapped[int] = mapped_column(ForeignKey("offshore_period_templates.id", ondelete="CASCADE"), nullable=False)
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    local_time: Mapped[object] = mapped_column(Time, nullable=False)
    service_code: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    work_position_id: Mapped[int | None] = mapped_column(ForeignKey("offshore_work_positions.id"), nullable=True)
    default_portions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint(
            "period_template_id",
            "day_offset",
            "local_time",
            "service_code",
            name="uq_offshore_period_template_events_template_day_time_code",
        ),
        Index("ix_offshore_period_template_events_template_sort", "period_template_id", "sort_order"),
        Index("ix_offshore_period_template_events_tenant_site", "tenant_id", "site_id"),
        CheckConstraint("day_offset >= 0", name="ck_offshore_period_template_events_day_offset_nonnegative"),
        CheckConstraint("length(trim(service_code)) > 0", name="ck_offshore_period_template_events_service_code_not_empty"),
        CheckConstraint("length(trim(display_name)) > 0", name="ck_offshore_period_template_events_display_name_not_empty"),
        CheckConstraint("default_portions IS NULL OR default_portions >= 0", name="ck_offshore_period_template_events_default_portions_nonnegative"),
    )


class OffshoreWorkPeriod(Base):
    __tablename__ = "offshore_work_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    period_template_id: Mapped[int | None] = mapped_column(ForeignKey("offshore_period_templates.id"), nullable=True)
    menu_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("offshore_menu_cycles.id"), nullable=True)
    start_menu_cycle_slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("offshore_menu_cycle_slots.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        Index("ix_offshore_work_periods_tenant_site_starts_at", "tenant_id", "site_id", "starts_at"),
        Index("ix_offshore_work_periods_tenant_site_ends_at", "tenant_id", "site_id", "ends_at"),
        Index("ix_offshore_work_periods_tenant_site_status", "tenant_id", "site_id", "status"),
        CheckConstraint("length(trim(name)) > 0", name="ck_offshore_work_periods_name_not_empty"),
        CheckConstraint("starts_at < ends_at", name="ck_offshore_work_periods_starts_before_ends"),
        CheckConstraint(
            "lower(status) IN ('draft', 'planned', 'active', 'completed', 'cancelled')",
            name="ck_offshore_work_periods_status_allowed",
        ),
    )


class OffshoreServiceEvent(Base):
    __tablename__ = "offshore_service_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    work_period_id: Mapped[int] = mapped_column(ForeignKey("offshore_work_periods.id", ondelete="CASCADE"), nullable=False)
    source_template_event_id: Mapped[int | None] = mapped_column(ForeignKey("offshore_period_template_events.id"), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    service_code: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    work_position_id: Mapped[int | None] = mapped_column(ForeignKey("offshore_work_positions.id"), nullable=True)
    expected_portions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint("work_period_id", "source_template_event_id", name="uq_offshore_service_events_period_source_template"),
        Index("ix_offshore_service_events_work_period_starts_at", "work_period_id", "starts_at"),
        Index("ix_offshore_service_events_tenant_site_status", "tenant_id", "site_id", "status"),
        CheckConstraint("length(trim(service_code)) > 0", name="ck_offshore_service_events_service_code_not_empty"),
        CheckConstraint("length(trim(display_name)) > 0", name="ck_offshore_service_events_display_name_not_empty"),
        CheckConstraint("expected_portions IS NULL OR expected_portions >= 0", name="ck_offshore_service_events_expected_portions_nonnegative"),
        CheckConstraint(
            "lower(status) IN ('planned', 'confirmed', 'completed', 'cancelled')",
            name="ck_offshore_service_events_status_allowed",
        ),
    )


class OffshorePrepTask(Base):
    __tablename__ = "offshore_prep_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    work_period_id: Mapped[int] = mapped_column(ForeignKey("offshore_work_periods.id", ondelete="CASCADE"), nullable=False)
    service_event_id: Mapped[int] = mapped_column(ForeignKey("offshore_service_events.id", ondelete="CASCADE"), nullable=False)
    builder_component_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    component_name_snapshot: Mapped[str | None] = mapped_column(String(240), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_time: Mapped[object | None] = mapped_column(Time, nullable=True)
    work_position_id: Mapped[int | None] = mapped_column(ForeignKey("offshore_work_positions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", server_default="planned")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        Index("ix_offshore_prep_tasks_tenant_site_date_status", "tenant_id", "site_id", "planned_date", "status", "sort_order"),
        Index("ix_offshore_prep_tasks_service_event_sort", "service_event_id", "sort_order"),
        Index("ix_offshore_prep_tasks_work_period_date", "work_period_id", "planned_date"),
        Index("ix_offshore_prep_tasks_work_position", "work_position_id"),
        CheckConstraint("length(trim(title)) > 0", name="ck_offshore_prep_tasks_title_not_empty"),
        CheckConstraint("sort_order >= 0", name="ck_offshore_prep_tasks_sort_order_nonnegative"),
        CheckConstraint(
            "lower(status) IN ('planned', 'in_progress', 'completed', 'cancelled')",
            name="ck_offshore_prep_tasks_status_allowed",
        ),
    )


class OffshoreWorkMenuDecision(Base):
    __tablename__ = "offshore_work_menu_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    service_event_id: Mapped[int] = mapped_column(ForeignKey("offshore_service_events.id", ondelete="CASCADE"), nullable=False)
    menu_track_key: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    selected_builder_composition_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    free_text: Mapped[str | None] = mapped_column(String(240), nullable=True)
    source_publication_pin_id: Mapped[str | None] = mapped_column(
        ForeignKey("commun_builder_publication_pins.id", ondelete="SET NULL"), nullable=True
    )
    source_publication_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source_publication_week: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint("tenant_id", "site_id", "service_event_id", "menu_track_key", name="uq_offshore_work_menu_decisions_event_track"),
        Index("ix_offshore_work_menu_decisions_tenant_site_event", "tenant_id", "site_id", "service_event_id"),
        Index("ix_offshore_work_menu_decisions_tenant_site_track", "tenant_id", "site_id", "menu_track_key"),
        CheckConstraint("length(trim(menu_track_key)) > 0", name="ck_offshore_work_menu_decisions_menu_track_key_not_empty"),
        CheckConstraint(
            "lower(decision_type) IN ('use_published', 'use_builder_composition', 'use_free_text')",
            name="ck_offshore_work_menu_decisions_decision_type_allowed",
        ),
        CheckConstraint("source_publication_year > 0", name="ck_offshore_work_menu_decisions_publication_year_positive"),
        CheckConstraint("source_publication_week BETWEEN 1 AND 53", name="ck_offshore_work_menu_decisions_publication_week_range"),
    )


class OffshoreServiceEventMenuContext(Base):
    __tablename__ = "offshore_service_event_menu_contexts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    work_period_id: Mapped[int] = mapped_column(ForeignKey("offshore_work_periods.id", ondelete="CASCADE"), nullable=False)
    service_event_id: Mapped[int] = mapped_column(
        ForeignKey("offshore_service_events.id", ondelete="CASCADE"), nullable=False
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    menu_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("offshore_menu_cycles.id"), nullable=True)
    start_menu_cycle_slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("offshore_menu_cycle_slots.id", ondelete="SET NULL"), nullable=True
    )
    menu_cycle_slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("offshore_menu_cycle_slots.id", ondelete="SET NULL"), nullable=True
    )
    menu_cycle_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(20), nullable=False)
    assignment_source: Mapped[str] = mapped_column(String(20), nullable=False)
    match_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    builder_publication_pin_id: Mapped[str | None] = mapped_column(
        ForeignKey("commun_builder_publication_pins.id", ondelete="SET NULL"), nullable=True
    )
    builder_publication_year: Mapped[int] = mapped_column(Integer, nullable=False)
    builder_publication_week: Mapped[int] = mapped_column(Integer, nullable=False)
    builder_menu_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    builder_menu_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint("service_event_id", name="uq_offshore_service_event_menu_contexts_service_event_id"),
        Index("ix_offshore_service_event_menu_contexts_tenant_site_date", "tenant_id", "site_id", "service_date"),
        Index("ix_offshore_service_event_menu_contexts_work_period", "work_period_id", "service_date"),
        Index("ix_offshore_service_event_menu_contexts_tenant_site_status", "tenant_id", "site_id", "resolution_status"),
        CheckConstraint("builder_publication_year > 0", name="ck_offshore_service_event_menu_contexts_publication_year_positive"),
        CheckConstraint("builder_publication_week BETWEEN 1 AND 53", name="ck_offshore_service_event_menu_contexts_publication_week_range"),
        CheckConstraint("menu_cycle_index IS NULL OR menu_cycle_index > 0", name="ck_offshore_service_event_menu_contexts_cycle_index_positive"),
        CheckConstraint("builder_menu_version IS NULL OR builder_menu_version > 0", name="ck_offshore_service_event_menu_contexts_builder_menu_version_positive"),
        CheckConstraint("lower(resolution_status) IN ('resolved', 'unresolved', 'unavailable', 'manual')", name="ck_offshore_service_event_menu_contexts_resolution_status_allowed"),
        CheckConstraint("lower(assignment_source) IN ('automatic', 'manual')", name="ck_offshore_service_event_menu_contexts_assignment_source_allowed"),
        CheckConstraint("match_status IS NULL OR lower(match_status) IN ('matched', 'missing', 'ambiguous', 'withdrawn')", name="ck_offshore_service_event_menu_contexts_match_status_allowed"),
    )
