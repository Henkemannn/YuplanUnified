from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template

inline_ui_bp = Blueprint("inline_ui", __name__, template_folder="templates", static_folder="static")


@inline_ui_bp.get("/ui/inline")
def inline_home():  # pragma: no cover simple render
    # Feature flag gate: inline_ui must be enabled (registry + tenant DB override logic is handled globally)
    registry = getattr(current_app, "feature_registry", None)
    if not registry or not registry.enabled("inline_ui"):
        # Standardized error schema
        return jsonify({"error": "not_found", "message": "Resource not available"}), 404
    return render_template("ui/notes_tasks.html")


@inline_ui_bp.get("/ui/inline-login")
def login_page():  # pragma: no cover
    registry = getattr(current_app, "feature_registry", None)
    if not registry or not registry.enabled("inline_ui"):
        return jsonify({"error": "not_found", "message": "Resource not available"}), 404
    return render_template("ui/login.html")
