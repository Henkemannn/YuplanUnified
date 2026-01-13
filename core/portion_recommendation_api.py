from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from .auth import require_roles
from .portion_recommendation_service import RecommendationInput

bp = Blueprint("portion_reco", __name__, url_prefix="/service")


@bp.post("/recommendation")
@require_roles("superuser", "admin", "cook", "unit_portal")
def recommendation():
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant"}), 400
    data = request.get_json(silent=True) or {}
    guest_count = data.get("guest_count")
    if guest_count is None:
        return jsonify({"ok": False, "error": "guest_count required"}), 400
    try:
        guest_count = int(guest_count)
    except Exception:
        return jsonify({"ok": False, "error": "invalid guest_count"}), 400
    inp = RecommendationInput(
        tenant_id=tenant_id,
        unit_id=data.get("unit_id") or session.get("unit_id"),
        category=data.get("category"),
        dish_id=data.get("dish_id"),
        guest_count=guest_count,
    )
    svc = current_app.portion_recommendation_service  # type: ignore[attr-defined]
    result = svc.recommend(inp)
    return jsonify(result)
