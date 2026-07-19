from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
