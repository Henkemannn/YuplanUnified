from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from core.auth import require_roles

from .db import get_session
from .models import Dish

bp = Blueprint("menu_api", __name__, url_prefix="/menu")


@bp.get("/week")
@require_roles("superuser", "admin", "cook")
def get_week():
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant"}), 400
    week = int(request.args.get("week", 0) or 0)
    year = int(request.args.get("year", 0) or 0)
    if not week or not year:
        return jsonify({"ok": False, "error": "week/year required"}), 400
    svc = current_app.menu_service  # type: ignore[attr-defined]
    view = svc.get_week_view(tenant_id, week, year)
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
    # Create or get menu
    menu_svc = current_app.menu_service  # type: ignore[attr-defined]
    menu = menu_svc.create_or_get_menu(tenant_id, week, year)
    # Optional on-the-fly dish creation
    if dish_id is None and dish_name:
        db = get_session()
        try:
            existing = db.query(Dish).filter_by(tenant_id=tenant_id, name=dish_name).first()
            if existing:
                dish_id = existing.id
            else:
                d = Dish(tenant_id=tenant_id, name=dish_name, category=None)
                db.add(d)
                db.commit()
                db.refresh(d)
                dish_id = d.id
        finally:
            db.close()
    try:
        mv_id = menu_svc.set_variant(tenant_id, menu.id, day, meal, variant_type, dish_id)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return {"ok": True, "menu_id": menu.id, "menu_variant_id": mv_id}
