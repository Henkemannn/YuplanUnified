"""SQLAlchemy model skeletons (no relationships wired yet)"""

from datetime import UTC, date, datetime
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional


class Base(DeclarativeBase):
    pass


# --- Tenancy & Users ---
class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))  # admin, unit_portal, cook, superuser
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), nullable=True)
    refresh_token_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

class Unit(Base):
    __tablename__ = "units"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(120))
    default_attendance: Mapped[int] = mapped_column(Integer, nullable=True)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(64))
    residence_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    resident_count_mode: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    resident_count_fixed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Residence(Base):
    __tablename__ = "residences"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# --- Menus & Dishes ---
class Dish(Base):
    __tablename__ = "dishes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), nullable=True)


class Recipe(Base):
    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=True)


class Menu(Base):
    __tablename__ = "menus"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    site_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    week: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


def _new_link_id() -> str:
    return str(uuid.uuid4())


class CommunBuilderMenuLink(Base):
    __tablename__ = "commun_builder_menu_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_link_id)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    legacy_menu_id: Mapped[int | None] = mapped_column(
        ForeignKey("menus.id", ondelete="SET NULL"), nullable=True
    )
    builder_menu_id: Mapped[str] = mapped_column(String(64), nullable=False)
    builder_menu_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "site_id", "year", "week", name="uq_commun_builder_menu_links_tenant_site_year_week"),
        CheckConstraint("year > 0", name="ck_commun_builder_menu_links_year_positive"),
        CheckConstraint("week BETWEEN 1 AND 53", name="ck_commun_builder_menu_links_week_range"),
        CheckConstraint("length(trim(builder_menu_id)) > 0", name="ck_commun_builder_menu_links_builder_menu_id_not_empty"),
        CheckConstraint("builder_menu_version > 0", name="ck_commun_builder_menu_links_builder_menu_version_positive"),
        CheckConstraint("projection_version > 0", name="ck_commun_builder_menu_links_projection_version_positive"),
        CheckConstraint("lower(source) IN ('manual', 'import', 'migration', 'pilot')", name="ck_commun_builder_menu_links_source_allowed"),
    )


class CommunBuilderPublicationPin(Base):
    __tablename__ = "commun_builder_publication_pins"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_link_id)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    legacy_menu_id: Mapped[int | None] = mapped_column(
        ForeignKey("menus.id", ondelete="SET NULL"), nullable=True
    )
    builder_menu_id: Mapped[str] = mapped_column(String(64), nullable=False)
    builder_menu_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    projection_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "site_id", "year", "week", name="uq_commun_builder_publication_pins_tenant_site_year_week"),
        CheckConstraint("year > 0", name="ck_commun_builder_publication_pins_year_positive"),
        CheckConstraint("week BETWEEN 1 AND 53", name="ck_commun_builder_publication_pins_week_range"),
        CheckConstraint("length(trim(builder_menu_id)) > 0", name="ck_commun_builder_publication_pins_builder_menu_id_not_empty"),
        CheckConstraint("builder_menu_version > 0", name="ck_commun_builder_publication_pins_builder_menu_version_positive"),
        CheckConstraint("lower(source) IN ('manual', 'import', 'migration', 'pilot')", name="ck_commun_builder_publication_pins_source_allowed"),
    )


class DepartmentMenuChoice(Base):
    __tablename__ = "department_menu_choices"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    meal: Mapped[str] = mapped_column(String(20), nullable=False, default="lunch", server_default="lunch")
    selected_variant: Mapped[str] = mapped_column(String(8), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "site_id",
            "department_id",
            "year",
            "week",
            "weekday",
            "meal",
            name="uq_department_menu_choices_business_key",
        ),
        CheckConstraint("year > 0", name="ck_department_menu_choices_year_positive"),
        CheckConstraint("week BETWEEN 1 AND 53", name="ck_department_menu_choices_week_range"),
        CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_department_menu_choices_weekday_range"),
        CheckConstraint("length(trim(selected_variant)) > 0", name="ck_department_menu_choices_selected_variant_not_empty"),
        CheckConstraint("lower(selected_variant) IN ('alt1', 'alt2')", name="ck_department_menu_choices_selected_variant_allowed"),
        CheckConstraint("lower(meal) = 'lunch'", name="ck_department_menu_choices_meal_lunch_only"),
    )


class DepartmentRequirementGroup(Base):
    __tablename__ = "department_requirement_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_link_id)
    department_id: Mapped[str] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint("default_quantity >= 0", name="ck_department_requirement_groups_default_quantity_non_negative"),
        Index("ix_department_requirement_groups_department_id", "department_id"),
    )


class DepartmentRequirementGroupRequirement(Base):
    __tablename__ = "department_requirement_group_requirements"

    group_id: Mapped[str] = mapped_column(
        ForeignKey("department_requirement_groups.id", ondelete="CASCADE"), primary_key=True
    )
    dietary_type_id: Mapped[int] = mapped_column(
        ForeignKey("dietary_types.id"), primary_key=True
    )

    __table_args__ = (
        Index("ix_department_requirement_group_requirements_dietary_type_id", "dietary_type_id"),
    )


class DepartmentRequirementGroupServiceOverride(Base):
    __tablename__ = "department_requirement_group_service_overrides"

    group_id: Mapped[str] = mapped_column(
        ForeignKey("department_requirement_groups.id", ondelete="CASCADE"), primary_key=True
    )
    service_date: Mapped[date] = mapped_column(Date, primary_key=True)
    meal_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_department_requirement_group_service_overrides_quantity_non_negative"),
        CheckConstraint(
            "length(trim(meal_key)) > 0",
            name="ck_department_requirement_group_service_overrides_meal_key_not_empty",
        ),
        CheckConstraint(
            "meal_key = lower(trim(meal_key))",
            name="ck_department_requirement_group_service_overrides_meal_key_normalized",
        ),
    )


class MenuVariant(Base):
    __tablename__ = "menu_variants"
    id: Mapped[int] = mapped_column(primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("menus.id"))
    day: Mapped[str] = mapped_column(String(10))  # Mån..Sön canonical
    meal: Mapped[str] = mapped_column(String(20))  # Lunch, Kväll, etc.
    variant_type: Mapped[str] = mapped_column(String(20))  # alt1, alt2, dessert, kvall
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"), nullable=True)


class MenuOverride(Base):
    __tablename__ = "menu_overrides"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date)
    meal: Mapped[str] = mapped_column(String(20))
    variant_type: Mapped[str] = mapped_column(String(20))
    replacement_dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(20))  # global, unit, private


# --- Diets & Attendance ---
class DietaryType(Base):
    __tablename__ = "dietary_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    diet_family: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantics: Mapped[str | None] = mapped_column(String(32), nullable=True)
    default_select: Mapped[bool] = mapped_column(Boolean, default=False)


class UnitDietAssignment(Base):
    __tablename__ = "unit_diet_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    dietary_type_id: Mapped[int] = mapped_column(ForeignKey("dietary_types.id"))
    count: Mapped[int] = mapped_column(Integer, default=0)


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    date: Mapped[date] = mapped_column(Date)
    meal: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(20), nullable=True)  # default / overridden / propagated


# --- Scheduling / Turnus ---
class ShiftTemplate(Base):
    __tablename__ = "shift_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(120))
    pattern_type: Mapped[str] = mapped_column(String(40))  # weekly / motor_v1 / simple6


class ShiftSlot(Base):
    __tablename__ = "shift_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=True)  # optional scope
    template_id: Mapped[int] = mapped_column(ForeignKey("shift_templates.id"), nullable=True)
    start_ts: Mapped[datetime] = mapped_column(DateTime)
    end_ts: Mapped[datetime] = mapped_column(DateTime)
    role: Mapped[str] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    notes: Mapped[str] = mapped_column(Text, nullable=True)


# --- Tasks (Prep / Freezer) ---
class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(30))  # prep / freezer / generic
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(20), default="todo"
    )  # todo|doing|blocked|done|cancelled
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    menu_id: Mapped[int] = mapped_column(ForeignKey("menus.id"), nullable=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"), nullable=True)
    private_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    creator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class TaskStatusTransition(Base):
    __tablename__ = "task_status_transitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    from_status: Mapped[str] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


# --- Messaging ---
class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    audience_type: Mapped[str] = mapped_column(String(30))  # all / unit / role
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Waste / Service Metrics ---
class PortionGuideline(Base):
    __tablename__ = "portion_guidelines"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(50))
    baseline_g_per_guest: Mapped[int] = mapped_column(Integer, nullable=True)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=True)


class ServiceMetric(Base):
    __tablename__ = "service_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    date: Mapped[date] = mapped_column(Date)
    meal: Mapped[str] = mapped_column(String(20))
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=True)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=True)
    produced_qty_kg: Mapped[float] = mapped_column(Float, nullable=True)
    served_qty_kg: Mapped[float] = mapped_column(Float, nullable=True)
    leftover_qty_kg: Mapped[float] = mapped_column(Float, nullable=True)
    served_g_per_guest: Mapped[float] = mapped_column(Float, nullable=True)


# --- Feature Flags (per tenant) ---
class TenantFeatureFlag(Base):
    __tablename__ = "tenant_feature_flags"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(80))  # e.g. module.offshore, waste.metrics
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Optional notes for admins; tests only require acceptance, not usage
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Updated timestamp used by tests for stale-state; default to utcnow
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


# --- Tenant Metadata ---
class TenantMetadata(Base):
    __tablename__ = "tenant_metadata"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), unique=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=True)  # municipal|offshore|demo|other
    description: Mapped[str] = mapped_column(String(255), nullable=True)


# --- Notes ---
class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    # Use timezone-aware UTC timestamps.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    private_flag: Mapped[bool] = mapped_column(Boolean, default=False)


# --- Audit Events ---
class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=True)
    event: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_audit_events_tenant_ts", "tenant_id", "ts"),
        Index("ix_audit_events_event_ts", "event", "ts"),
    )
