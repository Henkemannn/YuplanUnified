from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.auth import require_roles
from core.admin_user_repo import _resolve_user_scope

from .db import get_session

bp = Blueprint("menu_api", __name__, url_prefix="/menu")


def _resolve_site_id_for_testing(tenant_id: int) -> str | None:
    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        row = db.execute(
            text("SELECT id FROM sites WHERE tenant_id=:t ORDER BY id LIMIT 1"),
            {"t": tenant_id},
        ).fetchone()
        return str(row[0]) if row and row[0] else None
    finally:
        db.close()


def _variant_site_is_authorized(tenant_id: int, site_id: str) -> bool:
    """Require the requested site to match the authenticated user's scope."""
    user_id = session.get("user_id")
    role = str(session.get("role") or "").strip().lower()
    if not user_id:
        return False

    db = get_session()
    try:
        if role == "superuser":
            row = db.execute(
                text("SELECT tenant_id FROM sites WHERE id=:site_id LIMIT 1"),
                {"site_id": str(site_id)},
            ).fetchone()
            return bool(row and row[0] is not None and int(row[0]) == int(tenant_id))

        resolved_tenant_id, bound_site_id, valid_scope = _resolve_user_scope(
            db, int(user_id)
        )
        return bool(
            valid_scope
            and resolved_tenant_id == int(tenant_id)
            and bound_site_id == str(site_id).strip()
        )
    except (TypeError, ValueError, SQLAlchemyError):
        current_app.logger.exception("Unable to resolve menu variant site authorization")
        return False
    finally:
        db.close()


@bp.get("/week")
@require_roles("superuser", "admin", "cook", "kitchen")
def get_week():
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant"}), 400
    week = int(request.args.get("week", 0) or 0)
    year = int(request.args.get("year", 0) or 0)
    site_id = (
        request.args.get("site_id")
        or session.get("site_id")
        or request.headers.get("X-Site-Id")
    )
    if not site_id and current_app.config.get("TESTING"):
        site_id = _resolve_site_id_for_testing(tenant_id)
    if not week or not year:
        return jsonify({"ok": False, "error": "week/year required"}), 400
    if not site_id:
        return jsonify(
            {
                "type": "https://unified.example/errors/bad-request",
                "title": "Bad Request",
                "status": 400,
                "detail": "site_id required",
            }
        ), 400
    if not _variant_site_is_authorized(int(tenant_id), str(site_id)):
        return jsonify({"ok": False, "error": "site_forbidden"}), 403
    svc = current_app.menu_service  # type: ignore[attr-defined]
    view = svc.get_week_view(tenant_id, str(site_id), week, year)
    # Translate canonical keys to legacy labels expected by API tests
    def _legacy_day_label(d: str) -> str:
        m = {
            "mon": "Mon",
            "tue": "Tue",
            "wed": "Wed",
            "thu": "Thu",
            "fri": "Fri",
            "sat": "Sat",
            "sun": "Sun",
        }
        return m.get(d.strip().lower(), d)
    def _legacy_meal_label(mn: str) -> str:
        mn2 = mn.strip().lower()
        if mn2 == "lunch":
            return "Lunch"
        if mn2 == "dinner":
            return "Dinner"
        return mn
    days = view.get("days", {})
    translated_days: dict[str, dict[str, dict[str, dict]] ] = {}
    for dkey, meals in days.items():
        out_day = _legacy_day_label(dkey)
        translated_days[out_day] = {}
        for mkey, variants in meals.items():
            out_meal = _legacy_meal_label(mkey)
            translated_days[out_day][out_meal] = variants
    translated_view = {**view, "days": translated_days}
    return {"ok": True, "menu": translated_view}


@bp.post("/variant/set")
@require_roles("superuser", "admin", "cook")
def set_variant():
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant"}), 400
    data = request.get_json(silent=True) or {}
    required = ["week", "year", "day", "meal", "variant_type"]
    for r in required:
        if r not in data:
            return jsonify({"ok": False, "error": f"missing {r}"}), 400
    week = int(data["week"])
    year = int(data["year"])
    day = data["day"]
    meal = data["meal"]
    variant_type = data["variant_type"]
    dish_id = data.get("dish_id")
    dish_name = data.get("dish_name")
    if "site_id" in data and data["site_id"] is None:
        return jsonify(
            {
                "type": "https://unified.example/errors/bad-request",
                "title": "Bad Request",
                "status": 400,
                "detail": "site_id required",
            }
        ), 400
    site_id = (
        data.get("site_id")
        or session.get("site_id")
        or request.headers.get("X-Site-Id")
    )
    if not site_id:
        return jsonify(
            {
                "type": "https://unified.example/errors/bad-request",
                "title": "Bad Request",
                "status": 400,
                "detail": "site_id required",
            }
        ), 400
    if not _variant_site_is_authorized(tenant_id, str(site_id)):
        return jsonify(
            {
                "ok": False,
                "error": "site_unavailable",
                "status": 403,
            }
        ), 403
    menu_svc = current_app.menu_service  # type: ignore[attr-defined]
    try:
        menu_id, mv_id = menu_svc.set_variant_atomic(
            tenant_id=tenant_id,
            site_id=str(site_id),
            week=week,
            year=year,
            day=day,
            meal=meal,
            variant_type=variant_type,
            dish_id=dish_id,
            dish_name=dish_name,
        )
    except ValueError as exc:
        error_code = str(exc).split(":", 1)[0]
        if error_code == "menu_site_conflict":
            return jsonify(
                {
                    "ok": False,
                    "error": "menu_site_conflict",
                    "status": 409,
                }
            ), 409
        if error_code in {
            "site_tenant_mismatch",
            "menu_tenant_mismatch",
            "site_tenant_required",
        }:
            return jsonify(
                {
                    "ok": False,
                    "error": "site_unavailable",
                    "status": 403,
                }
            ), 403
        return jsonify({"ok": False, "error": str(exc)}), 400
    return {"ok": True, "menu_id": menu_id, "menu_variant_id": mv_id}
