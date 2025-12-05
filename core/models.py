"""SQLAlchemy model skeletons (no relationships wired yet)"""

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
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
    full_name: Mapped[str] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=True)
    refresh_token_jti: Mapped[str] = mapped_column(String(64), nullable=True)


class Unit(Base):
    __tablename__ = "units"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(120))
    default_attendance: Mapped[int] = mapped_column(Integer, nullable=True)


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
    week: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


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
    name: Mapped[str] = mapped_column(String(120))
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
