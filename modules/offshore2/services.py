from __future__ import annotations

from datetime import date as _date

from flask import current_app, request, session
from sqlalchemy import text

from core.context import get_active_context
from core.db import get_session, get_site_tenant

from .i18n import copy_for, normalize_locale, t
from .navigation import NAV_ITEMS, ROADMAP_ITEMS


def resolve_locale() -> str:
    requested = (request.args.get("lang") or session.get("offshore_locale") or "").strip().lower()
    locale = normalize_locale(requested)
    return locale


def resolve_theme() -> str:
    theme = (session.get("offshore_theme") or "light").strip().lower()
    if theme not in ("system", "light", "dark"):
        return "light"
    return theme


def _lookup_names(tenant_id: int | None, site_id: str | None) -> tuple[str | None, str | None]:
    tenant_name = None
    site_name = None
    db = get_session()
    try:
        if tenant_id is not None:
            row = db.execute(text("SELECT name FROM tenants WHERE id = :id"), {"id": int(tenant_id)}).fetchone()
            if row and row[0]:
                tenant_name = str(row[0])
        if site_id:
            row = db.execute(text("SELECT name FROM sites WHERE id = :id"), {"id": str(site_id)}).fetchone()
            if row and row[0]:
                site_name = str(row[0])
    finally:
        db.close()
    return tenant_name, site_name


def resolve_active_context() -> dict[str, object]:
    ctx = get_active_context()
    tenant_id = ctx.get("tenant_id")
    session_site_id = ctx.get("site_id")
    requested_site_id = (request.args.get("site_id") or "").strip() or None

    if not session_site_id:
        return {"redirect": True, "reason": "missing_site"}

    if requested_site_id and requested_site_id != session_site_id:
        return {"redirect": False, "forbidden": True, "reason": "site_mismatch"}

    db_site_tenant = None
    try:
        db_site_tenant = get_site_tenant(str(session_site_id))
    except Exception:
        db_site_tenant = None

    if tenant_id is not None and db_site_tenant is not None and int(db_site_tenant) != int(tenant_id):
        return {"redirect": False, "forbidden": True, "reason": "tenant_mismatch"}

    tenant_name, site_name = _lookup_names(tenant_id, session_site_id)
    return {
        "redirect": False,
        "forbidden": False,
        "tenant_id": tenant_id,
        "site_id": session_site_id,
        "tenant_name": tenant_name,
        "site_name": site_name,
    }


def build_vm(*, locale: str, theme: str, role: str | None, tenant_id: int | None, site_id: str | None, tenant_name: str | None, site_name: str | None) -> dict[str, object]:
    labels = copy_for(locale)
    return {
        "lang": locale,
        "theme": theme,
        "labels": labels,
        "nav_items": [{**item, "label": t(locale, item["label_key"])} for item in NAV_ITEMS],
        "tenant_id": tenant_id,
        "site_id": site_id,
        "tenant_name": tenant_name,
        "site_name": site_name,
        "user_name": session.get("full_name") or session.get("username") or session.get("user_email") or "Inloggad",
        "user_role": role,
        "can_manage": (role or "").strip().lower() in ("admin", "superuser"),
        "roadmap_items": [t(locale, key) for key in ROADMAP_ITEMS],
        "support_mail": "mailto:support@yuplan.se",
        "today": _date.today().isoformat(),
        "allow_site_switch": (role or "").strip().lower() in ("admin", "superuser"),
        "shell_brand": labels["offshore.brand"],
    }


def build_dashboard_vm(locale: str, theme: str, role: str | None, tenant_id: int | None, site_id: str | None, tenant_name: str | None, site_name: str | None) -> dict[str, object]:
    vm = build_vm(
        locale=locale,
        theme=theme,
        role=role,
        tenant_id=tenant_id,
        site_id=site_id,
        tenant_name=tenant_name,
        site_name=site_name,
    )
    vm.update(
        {
            "page_title": vm["labels"]["offshore.dashboard.title"],
            "page_subtitle": vm["labels"]["offshore.dashboard.subtitle"],
            "empty_title": vm["labels"]["offshore.dashboard.no_active_period"],
            "empty_body": vm["labels"]["offshore.dashboard.no_active_period_body"],
            "today_placeholder": vm["labels"]["offshore.dashboard.today_placeholder"],
            "cta_label": vm["labels"]["offshore.dashboard.open_settings"],
            "roadmap_title": vm["labels"]["offshore.dashboard.roadmap"],
        }
    )
    return vm


def build_settings_vm(locale: str, theme: str, role: str | None, tenant_id: int | None, site_id: str | None, tenant_name: str | None, site_name: str | None) -> dict[str, object]:
    vm = build_vm(
        locale=locale,
        theme=theme,
        role=role,
        tenant_id=tenant_id,
        site_id=site_id,
        tenant_name=tenant_name,
        site_name=site_name,
    )
    sections = [
        {"title": vm["labels"]["offshore.settings.installation"], "body": vm["labels"]["offshore.settings.placeholder"], "status": vm["labels"]["offshore.settings.coming_later"]},
        {"title": vm["labels"]["offshore.settings.period_templates"], "body": vm["labels"]["offshore.settings.placeholder"], "status": vm["labels"]["offshore.settings.coming_later"]},
        {"title": vm["labels"]["offshore.settings.work_positions"], "body": vm["labels"]["offshore.settings.work_positions_body"], "status": vm["labels"]["offshore.settings.coming_later"]},
        {"title": vm["labels"]["offshore.settings.menu_cycle"], "body": vm["labels"]["offshore.settings.placeholder"], "status": vm["labels"]["offshore.settings.coming_later"]},
        {"title": vm["labels"]["offshore.settings.default_portions"], "body": vm["labels"]["offshore.settings.placeholder"], "status": vm["labels"]["offshore.settings.coming_later"]},
        {"title": vm["labels"]["offshore.settings.permissions"], "body": vm["labels"]["offshore.settings.placeholder"], "status": vm["labels"]["offshore.settings.coming_later"]},
    ]
    vm.update(
        {
            "page_title": vm["labels"]["offshore.settings.title"],
            "page_subtitle": vm["labels"]["offshore.settings.subtitle"],
            "sections": sections,
        }
    )
    return vm
