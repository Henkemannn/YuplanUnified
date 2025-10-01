from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from .auth import require_roles

bp = Blueprint("service_recommendation", __name__, url_prefix="/service")

@bp.get("/recommendation")
@require_roles("superuser","admin","cook","unit_portal")
def get_recommendation():
    tenant_id = session.get("tenant_id")
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant"}), 400
    category = request.args.get("category")
    guest_count = request.args.get("guest_count")
    week = request.args.get("week")
    if not category or guest_count is None:
        return jsonify({"ok": False, "error": "category and guest_count required"}), 400
    try:
        guest_count = int(guest_count)
    except Exception:
        return jsonify({"ok": False, "error": "invalid guest_count"}), 400
    svc = current_app.portion_service  # type: ignore[attr-defined]
    blended = svc.blended_g_per_guest(tenant_id, category, week=week)
    protein_per_100g = svc.protein_per_100g(tenant_id, category)
    total_gram = guest_count * blended.recommended_g_per_guest
    total_protein = None
    if protein_per_100g is not None:
        total_protein = (protein_per_100g / 100.0) * total_gram
    return jsonify({
        "category": category,
        "guest_count": guest_count,
    "recommended_g_per_guest": blended.recommended_g_per_guest,
        "total_gram": total_gram,
        "total_protein": total_protein,
        "source": blended.source,
        "sample_size": blended.sample_size,
        "baseline_used": blended.baseline_used,
        "history_mean_raw": blended.history_mean_raw,
        "history_mean_used": blended.history_mean_used
    })
